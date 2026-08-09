# Supported Features for the SHACL to Flink transformation

## Target Nodes

SHACL defines a mechanism to select the node which is validated. The following mechanisms are supported


<table>
<tr>
<th> Feature </th>
<th> Example </th>
<th> Implemented </th>
</tr>
<tr>
<td>

```turtle
sh:targetNode
```
</td>
<td>

```turtle
cutterTemperatureShape a sh:NodeShape ;
    sh:targetClass iffbase:Cutter ;
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
</table>


## Constraint Components

<table>

<tr>
<th> Feature </th>
<th> Example </th>
<th> Implemented </th>
</tr>

<tr>
<td>

```turtle
sh:class
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasState ;
        sh:property [
            sh:class ontology:MachineState ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>

<tr>
<td>

```turtle
sh:datatype
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:datatype xsd:double ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:nodeKind
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:nodeKind sh:Literal ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:minCount
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:minCount 1 ;
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:maxCount
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:maxCount 1 ;
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:minExclusive
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:minExclusive 20.0 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:minInclusive
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:minExclusive 20.0 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:maxExclusive
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:maxExclusive 50.0 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:maxInclusive
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasTemperature ;
        sh:property [
            sh:maxInclusive 50.0 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:minLength
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasStringExample ;
        sh:property [
            sh:minLength 5 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:maxLength
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasStringExample ;
        sh:property [
            sh:maxLength 5 ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:pattern
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasStringExample ;
        sh:property [
            sh:pattern "^1\\.\\d{4,5}" ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:in
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasStringExample ;
        sh:property [
            sh:in ("Hello" "World") ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:hasValue
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:path iffbase:hasStringExample ;
        sh:property [
            sh:hasValue "Hello World" ;
        ]
    ] .
```

</td>
<td style="font-size: 50px;color: red">&#10007;</td>
</tr>
<tr>
<td>

```turtle
sh:not
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:not
        [
            sh:property [
                sh:path iffbase:hasTemperature ;
                sh:property [
                    sh:maxInclusive 50.0 ;
                ]
            ]
        ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:or
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:or (
        [
            sh:property [
                sh:path iffbase:hasTemperature ;
                sh:property [
                    sh:maxInclusive 50.0 ;
                ]
            ]
        ]
        [
            sh:property [
                sh:path iffbase:hasTemperature2 ;
                sh:property [
                    sh:minInclusive 20.0 ;
                ]
            ]
        ]
    ) .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:and
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:and (
        [
            sh:property [
                sh:path iffbase:hasTemperature ;
                sh:property [
                    sh:maxInclusive 50.0 ;
                ]
            ]
        ]
        [
            sh:property [
                sh:path iffbase:hasTemperature2 ;
                sh:property [
                    sh:minInclusive 20.0 ;
                ]
            ]
        ]
    ) .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:xone
```

</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:xone (
        [
            sh:property [
                sh:path iffbase:hasTemperature ;
                sh:property [
                    sh:maxInclusive 50.0 ;
                ]
            ]
        ]
        [
            sh:property [
                sh:path iffbase:hasTemperature2 ;
                sh:property [
                    sh:minInclusive 20.0 ;
                ]
            ]
        ]
    ) .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:sparql
```
</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:targetClass iffbase:Cutter ;
    sh:sparql [
        a sh:SPARQLConstraint ;
        sh:select """
        """
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:message
```
</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:targetClass iffbase:Cutter ;
    sh:sparql [
        sh:message "Cutter {?this} executing without executing filter {?filter}" ;
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```turtle
sh:severity
```
</td>
<td>

```turtle
:demoShape a sh:NodeShape ;
    sh:property [
        sh:severity iffbase:severityCritical ] ;
        sh:path iffbase:hasAttribute ;
    ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
</table>

## Sparql based constraints

### Sparql Query

The following SPARQL features are supported

<table>
<tr>
<th> Feature </th>
<th> Example </th>
<th> Implemented </th>
</tr>
<tr>
<td>

```
Basic Graph Pattern (BGP)
```
</td>
<td>

```sparql
    ?this iffbase:hasFilter [ ngsi-ld:hasObject ?filter ] .
    ?this iffbase:hasState [ ngsi-ld:hasValue ?cstate ] .
    ?filter iffbase:hasState [ ngsi-ld:hasValue ?fstate ] .
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```

OPTIONAL {}
(only single triple supported)
```
</td>
<td>

```sparql
OPTIONAL{ ?this iffbase:hasFilter [ ngsi-ld:hasObject ?filter ] }
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
BIND
```
</td>
<td>

```turtle
BIND("hello world") as ?value
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
BOUND
```
</td>
<td>

```turtle
BOUND(?value)
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
IF
```
</td>
<td>

```turtle
IF(condition, true, false)
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
FILTER
```
</td>
<td>

```turtle
FILTER (?cstate = ontology:executingState && ?fstate != ontology:executingState)
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
ConditionalOrExpression
```
</td>
<td>

```turtle
?cstate = ontology:executingState || ?fstate != ontology:executingState
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
ConditionalAndExpression
```
</td>
<td>

```turtle
?cstate = ontology:executingState && ?fstate != ontology:executingState
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
RelationalExpression
(=, !=, <,>, <=, >=, IN, NOT IN)
```
</td>
<td>

```turtle
?x > 5 
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
JOIN
```
</td>
<td>

```sparql
{BGP}
{BGP}
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
NOT EXISTS
```
</td>
<td>

```turtle
    FILTER NOT EXISTS{
        BGP
    }

```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
DISTINCT
```
</td>
<td>

```turtle
SELECT DISTINCT ?value
    WHERE {}
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>

<tr>
<td>

```
Now
```
</td>
<td>

```turtle
NOW()
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
CAST
(xsd:integer, xsd:float, xsd:dateTime, xsd:string)
```
</td>
<td>

```turtle
xsd:integer(?value)
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
Additive Expression
```
</td>
<td>

```turtle
?value1 + ?value2
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
UnaryNot
```
</td>
<td>

```turtle
!(?value)
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
<tr>
<td>

```
Multiplicative Expression
(*, /)
```
</td>
<td>

```turtle
?value1 * ?value2
```

</td>
<td style="font-size: 50px;color: green;">&#10003;</td>
</tr>
</table>

## Attribute nesting depth

NGSI-LD attributes may carry sub-attributes. Constraints can target them, but
only to **one level below the attribute**:

| shape | supported |
|---|---|
| `attribute` (e.g. `temperature`) | yes |
| `attribute -> sub-attribute` (e.g. `assembly -> torque`) | yes |
| `relationship -> sub-attribute` (e.g. `hasPart -> trust`) | yes |
| `attribute -> sub -> sub-sub` (e.g. `assembly -> torque -> precision`) | **no** |

A sub-attribute of a *relationship* works exactly like one of a property: the
parent is matched on `parentId`, so the parent's own type does not matter. This
is the usual NGSI-LD pattern of a relationship carrying metadata such as trust
or confidence.

The limit is two separate things, so raising it is not a one-line change:

1. `MAX_SUBPROPERTY_DEPTH` in `lib/shacl_properties_to_sql.py` rejects deeper
   paths during extraction.
2. `constraint_table` has exactly two path columns (`propertyPath`,
   `subpropertyPath`) and the generated SQL has exactly two `attributes_view`
   joins -- one for the attribute, one for the sub-attribute. There is nowhere
   to put a third path and no join to traverse it.

Supporting arbitrary depth would mean deriving the deepest chain from the
shapes at build time and unrolling that many path columns and joins, in the
same way the constraint circuit is unrolled one statement per level.

> **Caution:** a shape that is too deep is currently reported as a warning on
> stdout and then skipped, and the build still succeeds. Validation therefore
> reports *conformant* for a constraint that was never checked. Do not rely on
> a deep shape being enforced without checking the build output.

## Logical constraint components

`sh:and`, `sh:or`, `sh:not` and `sh:xone` are supported both **on a property
shape** (constraining the values of one path) and **on a node shape** (grouping
whole shapes, so each branch may constrain a different property):

```turtle
:CutterShape a sh:NodeShape ; sh:targetClass :Cutter ;
  sh:or ( [ sh:property [ sh:path :hasTemp   ; ... sh:maxInclusive 50 ] ]
          [ sh:property [ sh:path :hasCoolant ; ... sh:minCount 1     ] ] ) .
```

They are compiled into a boolean circuit (`constraint_table.operation` plus the
`constraint_combination_table` edge list) and evaluated one SQL statement per
circuit level, so nesting is not limited to one level.

**Recursive shapes are rejected at build time.** A cycle has no finite circuit,
and Flink SQL has no fixpoint with which to evaluate one.

### Construct
TBD