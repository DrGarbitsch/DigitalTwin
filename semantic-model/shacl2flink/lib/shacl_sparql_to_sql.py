from rdflib import Graph
import os
import sys
import re
import ruamel.yaml
from jinja2 import Template


file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import configs  # noqa: E402
import utils  # noqa: E402
from sparql_to_sql import translate_sparql  # noqa: E402

yaml = ruamel.yaml.YAML()
alerts_bulk_table = configs.alerts_bulk_table_name
alerts_bulk_table_object = configs.alerts_bulk_table_object_name
constraint_trigger_table_name = configs.constraint_trigger_table_name

sparql_get_all_sparql_nodes = """
SELECT ?nodeshape ?targetclass ?message ?select ?severitylabel
where {
    ?nodeshape a sh:NodeShape .
    ?nodeshape sh:targetClass ?targetclass .
    ?nodeshape sh:sparql [
            sh:message ?message ;
            sh:select ?select ;
            ] ;

    OPTIONAL {
        ?nodeshape sh:sparql [
            sh:severity ?severity ;
        ] .
        ?severity rdfs:label ?severitylabel .
    }
}
"""

"""
A SPARQL constraint is a leaf of the same constraint circuit the core SHACL
checks feed, so it emits into `constraint_trigger_table` rather than raising its
own alert, and the shared PUBLISH step turns it into an alert.

That makes the focus-node universe join redundant. The previous form wrapped the
compiled query in `<targetclass>_view LEFT JOIN (query)` purely to emit an
'ok' row for every focus node that did not violate. Circuit leaves are sparse -
they emit violations only - and an alert clears by retraction when the row
disappears, exactly as the core leaves already behave. The class of `?this` is
not lost with the wrapper: translate_query injects
`?this rdf:type/rdfs:subClassOf <targetclass>` into the BGP itself.
"""
sql_check_sparql_base = """
            INSERT {% if sqlite %}OR REPlACE{% endif %} INTO {{constraint_trigger_table}}
            SELECT
                `this` AS resource,
                'SPARQLConstraintComponent({{nodeshape}})' AS event,
                {{constraint_id}} AS constraint_id,
                true AS triggered,
                '{{severity}}' AS severity,
                '{{message}}' as `text`
                {%- if sqlite %}
                ,CURRENT_TIMESTAMP
                {%- endif %}
            FROM ({{sql_expression}})
"""  # noqa E501


def add_variables_to_message(message):
    """Replace ?vars or $vars with SQL term

    For instance: "value is {?value}!" => "value is " || IFNULL(`value`, 'NULL') || '!'
    Args:
        message (string): string with {?var} or {$var} definition

    Returns:
        string: Adapted string
    """
    return re.sub(r"\{([\?\$])(\w*)\}", r"' || IFNULL(`\2`, 'NULL') || '", message)


def translate(shaclfile, knowledgefile, prefixes, first_constraint_id=0):
    """
    Translate shacl sparql constraints into SQL constraints.

    Parameters:
        shaclname: filename of SHACL file
        knowledgename: filename of knowledge file
        first_constraint_id: first free id in the shared constraint circuit

    Returns:
        sql-statement-list: list of plain SQL objects
        (statementset, tables, views, constraint_checks, constraint_combination,
         next_constraint_id): statementset in yaml format, plus the circuit rows
        these constraints contribute. The caller passes them to the property
        translation, which owns emitting constraint_table.

    """
    g = Graph(store="Oxigraph")
    h = Graph(store="Oxigraph")
    g.parse(shaclfile)
    h.parse(knowledgefile)
    g += h
    g = utils.transitive_closure(g)
    tables_all = []
    statementsets = []
    constraint_checks = []
    constraint_combination = []
    constraint_id_counter = first_constraint_id
    sqlite = ''
    # Get all SHACL NODES using SPARQL
    qres = g.query(sparql_get_all_sparql_nodes, initNs=prefixes)
    for row in qres:
        target_class = row.targetclass
        message = row.message.toPython() if row.message else None
        select = row.select.toPython() if row.select else None
        nodeshape = utils.strip_class(row.nodeshape.toPython()) if row.nodeshape else None
        severitylabel = row.severitylabel.toPython() if row.severitylabel is not None else 'warning'
        sql_expression, tables = translate_sparql(shaclfile, knowledgefile, select, target_class, g)
        sql_expression_yaml = utils.process_sql_dialect(sql_expression, False)
        sql_expression_sqlite = utils.process_sql_dialect(sql_expression, True)

        constraint_id = constraint_id_counter
        constraint_id_counter += 1
        check = utils.init_constraint_check()
        check['id'] = constraint_id
        check['targetClass'] = target_class.toPython() if target_class is not None else None
        check['severity'] = severitylabel
        constraint_checks.append(check)
        # A SPARQL constraint is always its own circuit root: sh:sparql cannot
        # currently appear underneath sh:and/sh:or/sh:not, so it publishes
        # directly. Once it can, this edge is what a connective would replace.
        constraint_combination.append({'operation': 'PUBLISH',
                                       'member_constraint_id': constraint_id,
                                       'target_constraint_id': -1})

        render_args = {
            'constraint_trigger_table': constraint_trigger_table_name,
            'constraint_id': constraint_id,
            'message': add_variables_to_message(message),
            'nodeshape': nodeshape,
            'severity': severitylabel,
        }
        sql_command_yaml = Template(sql_check_sparql_base).render(
            sql_expression=sql_expression_yaml, sqlite=False, **render_args)
        sql_command_sqlite = Template(sql_check_sparql_base).render(
            sql_expression=sql_expression_sqlite, sqlite=True, **render_args)

        sql_command_sqlite += ";"
        sql_command_yaml += ";"
        sqlite += sql_command_sqlite
        statementsets.append(sql_command_yaml)
        tables_all += map(utils.snake_case_to_kebab_case, tables)

    views = []
    tables = list(set(tables_all))
    for table in tables:
        if table != configs.rdf_table_obj_name:
            views.append(f'{table}-view')
    tables.append(alerts_bulk_table_object)
    tables.append(configs.constraint_trigger_table_object_name)
    tables.append(configs.rdf_table_name)
    return sqlite, (statementsets, tables, views, constraint_checks,
                    constraint_combination, constraint_id_counter)
