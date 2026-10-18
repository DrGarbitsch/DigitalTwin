# Static and dynamic OPC UA nodes: challenges

Analysis of the 20 nodesets of `translate_default_nodesets.make` (UA-Nodeset `UA-1.05.03-2023-12-15`: core,
15 companion specifications, 4 instance examples), 28,086 nodes, 664 of them dynamic. All numbers are reproducible with the scripts in
[`static-dynamic-analysis/`](static-dynamic-analysis/), the full evidence is the generated
[data report](static-dynamic-analysis/report.md).

The analysis uses the standard classification (R3 NamespaceMetadata rule, R5 default rule), i.e.
`nodeset2owl.py --strict-classification`. Since then nodeset2owl.py applies by default the heuristic rules R1
(instance-with-Variables), R2 (containment) and R4 (definition rule), see the
[README](../README.md#static-and-dynamic-nodes). They resolve the server state on static nodes found below (and
`OnlineAccess`, `Aliases/LastChange`) as well as the misclassified type system nodes of PackML, ISA95 and IRDI; all
reclassified nodes are listed in [classification-changes.md](static-dynamic-analysis/classification-changes.md),
the evaluation is in [heuristic-outliers.md](static-dynamic-analysis/heuristic-outliers.md).

## Key messages

1. **Dynamic nodes are not only the Server object.** In core, all 116 dynamic nodes belong to the Server object
   (decided by core's NamespaceMetadata). The companion specifications contain *no* Server-related dynamic nodes:
   their dynamic nodes are either real instances (example nodesets, correct) or **misclassified type system nodes
   and dictionary entries** (PackML, ISA95, IRDI), caused by missing or empty NamespaceMetadata.
2. **Static is not only a question of the NodeId.** A static node gets *one* global identity, so every statement
   about it must hold in every server. 615 static nodes live inside dynamic (server specific) structures; 443 of them
   are fine (constants, structure), but **172 carry server state** on a global node: DI's `MaxInactiveLockTime`
   (described by DI itself as *"Server-specific period of time"*), core's `ServerConfiguration/ApplicationUri`, the
   identity mappings of the well-known roles, PubSub status and diagnostics, historian defaults.
3. **The structural view is not enough.** DI's `DeviceTopology/OnlineAccess` (*"whether the Server is currently able
   to communicate"*) and core's `Objects/Aliases/LastChange` are runtime state on static nodes *outside* any
   dynamic structure; only a value-based check finds them.
4. **NamespaceMetadata quality decides.** Where it is maintained (core, DI, Pumps, TMC, …) the classification is
   right; where it is empty (PackML, IRDI, examples) or broken (ISA95-JobControl: `StaticStringNodeIdPattern = "0"`)
   the fallback rule has to guess, and guesses wrong for the type system.

## Background

- **Identification**: every node has the IRI `<namespace>` + base64url(canonical ExpandedNodeId). Static nodes
  are server independent; dynamic nodes only exist in a server, their ExpandedNodeId contains the server URI
  (`svu=…;nsu=…;i=…`).
- **Classification**: the NamespaceMetadata of the namespace (`StaticNodeIdTypes`, `StaticNumericNodeIdRange`,
  `StaticStringNodeIdPattern`) decides where it covers the IdType; otherwise the **fallback rule**: type nodes and
  instance declarations are static, all other instances dynamic.
- **Consequence for composition**: without server URI (global version of a companion specification) dynamic nodes
  and all references to them are left out. When the knowledge of several servers is composed, a static node is
  *shared*: it gets one parent per server and – if it carries server state – one value per server.

## 1. Where do the dynamic nodes come from?

| Namespace | static | dynamic | Dynamic subtrees (root → nodes) | Reason | Verdict |
|---|---|---|---|---|---|
| core | 4,840 | 116 | `Server` (ServerType) → 113; 3 orphans `CurrentServerId`, `ServerUriArray`, `ServerNetworkGroups` (SymbolicName `Server_ServerRedundancy_…`, no reference in the nodeset) | NamespaceMetadata (36 static ranges) | ✔ Server object |
| Machinery_Example | 35 | 38 | `ExampleMachine01` → 30; own NamespaceMetadata object → 8 | fallback (metadata decides nothing) | ✔ instance / ✘ metadata object |
| LaserSystem-Example | 0 | 91 | `LaserSystem-Example` → 83; NamespaceMetadata → 8 | fallback | ✔ instance / ✘ metadata object |
| MachineTool-Example | 0 | 119 | `SampleMachineTool` → 73, `SampleMachineTool_v101` → 38; NamespaceMetadata → 8 | fallback | ✔ instances / ✘ metadata object |
| Pump InstanceExample | 0 | 184 | `ExamplePump` → 184 | fallback (no metadata) | ✔ instance |
| **PackML** | 211 | 37 | 2 TypeDictionaries → 16, 12 encoding objects, `PackMLObjects` folder → 1, own NamespaceMetadata → 8 | fallback (metadata decides nothing) | ✘ type system, ✘ entry folder, ✘ metadata |
| **ISA95** | 368 | 20 | 2 TypeDictionaries → 12, 8 encoding objects | fallback (no metadata) | ✘ type system |
| **Dictionary/IRDI** | 0 | 59 | 51 IRDI dictionary entries (each its own root below core's `Dictionaries`), NamespaceMetadata → 8 | fallback (metadata decides nothing) | ✘ dictionary entries, ✘ metadata |
| DEXPI, DI, IA, ISA95-JobControl, LaserSystems, MachineTool, Machinery, ProcessValues, Result, PADIM, Pumps, TMC | 21,968 | 0 | – | NamespaceMetadata | ✔ |

**Answer:** no, only core's dynamic nodes stem from the Server object. In the companion specifications, dynamic
nodes are either *real instances* (examples – they hang below the static global folder `Machines`, exactly as
intended) or **misclassifications by the fallback rule**:

- type system nodes (encodings, type dictionaries) – section 4,
- IRDI dictionary entries – global concepts by definition (an IRDI *is* a global identifier),
- the entry folder `PackMLObjects` (organized by `Objects`; compare Machinery's `Machines`, which Machinery's
  NamespaceMetadata declares static),
- the NamespaceMetadata objects of PackML, IRDI and the examples themselves: their metadata says nothing, so the
  metadata object becomes dynamic and **the global version of the specification has no NamespaceMetadata at all**.

Metadata quality findings on the way:

| Namespace | Finding |
|---|---|
| PackML, IRDI, Machinery_Example, LaserSystem-Example, MachineTool-Example | NamespaceMetadata present, but `StaticNodeIdTypes`, `StaticNumericNodeIdRange` and `StaticStringNodeIdPattern` are empty – the metadata decides nothing |
| ISA95 (2013), Pump InstanceExample | no NamespaceMetadata |
| ISA95-JobControl | `StaticStringNodeIdPattern = "0"` – a regular expression matching only the string id `"0"`, almost certainly unintended (no effect today: all ids are numeric) |
| core | 3 ServerRedundancy properties without any reference (orphans) |

## 2. Static nodes inside dynamic structures

615 static nodes have a dynamic node above them. They form 33 groups, each below one *boundary* node (the static
node directly below the dynamic one). Categories (rules in `analyze.py`, `category()`):

| Category | Nodes | Semantics | Verdict |
|---|---|---|---|
| constant: method signature | 148 | `InputArguments`/`OutputArguments` of methods – fixed by the specification | ✔ |
| constant: namespace description | 92 | `NamespaceUri`, version, publication date, static NodeId rules of a NamespaceMetadata object | ✔ |
| constant: diagnostics counter metadata | 16 | `Classification`/`DiagnosticsLevel` of PubSub diagnostics counters – fixed per counter by Part 14 | ✔ |
| structure: object/method without value | 187 | folders, objects, methods – no value of their own | ✔ (their variables are judged individually) |
| server state: security configuration | 6 | `DefaultRolePermissions`, `DefaultUserRolePermissions`, `DefaultAccessRestrictions` of NamespaceMetadata (core, DI) | ✘ |
| server state: configuration, capability or runtime value | 166 | see below | ✘ |

### Review of the groups

| Group (dynamic parent / boundary) | Static nodes | Semantics (specification) | Verdict |
|---|---|---|---|
| `Namespaces` / NamespaceMetadata objects of 12 companion specifications and core | 111 | Describe the namespace (URI, version, date, static NodeId rules). Identical in every server that has the namespace – the object is a *description of the namespace*, not of the server. Only its link from the server's `Namespaces` folder is server specific. | ✔ constants |
| … within core and DI metadata: `DefaultRolePermissions`, `DefaultUserRolePermissions`, `DefaultAccessRestrictions` | 6 | Default permissions/restrictions for all nodes of the namespace (Part 3/5) – **configured per server** by its administrator; `DefaultUserRolePermissions` even depends on the session user. | ✘ server security configuration |
| `ServerCapabilities` / DI `MaxInactiveLockTime` | 1 | DI's own description: *"Server-specific period of time in milliseconds until the Server will revoke a lock."* A sibling of core's ServerCapabilities properties (`MaxSessions`, `MaxArrayLength`, …), which core – correctly – declares dynamic. DI's metadata declares the whole namespace static (`1:2147483647`). | ✘ **the clearest case: the specification itself calls the value server specific** |
| `RoleSet` / the 11 well-known roles (`Anonymous`, `Operator`, `Engineer`, `SecurityAdmin`, …) | 208 | Part 18 defines well-known roles with fixed NodeIds so that clients find "the Operator role" in every server – the **role concept** is legitimately global. But `Identities`, `Applications`, `Endpoints`, `…Exclude`, `CustomConfiguration` are the **per-server mapping** of users, applications and endpoints to the role. Method arguments (`AddIdentity`, …) are constants. | ✘ 65 mapping variables / ✔ role identity, methods |
| `Server` / `ServerConfiguration` | 135 | Part 12 push management: `ApplicationUri` and `ProductUri` (the server's own identity – the `ApplicationUri` *is* the server URI used as `svu`!), `ApplicationType`, `ServerCapabilities`, `SupportedPrivateKeyFormats`, `MaxTrustListSize`, `MulticastDnsEnabled`, `HasSecureElement`, certificate groups with `CertificateTypes` and TrustList file state (`Size`, `OpenCount`, `Writable`, `UserWritable`, `LastUpdateTime`), `UserManagement` (`Users`, password policy). | ✘ 30 variables – server identity, security configuration and state |
| `Server` / `PublishSubscribe` | 125 | Part 14: capabilities (`MaxPubSubConnections`, `MaxDataSetWriters`, …, `SupportSecurityKey…`), `SupportedTransportProfiles`, `ConfigurationVersion`, `ConfigurationProperties`, `DefaultDatagramPublisherId`, `DefaultSecurityKeyServices`, `Status/State`, diagnostics (`TotalError`, `TotalInformation`, `SubError`, live values, counter states and `Active` flags), `PubSubConfiguration` file state. | ✘ 52 variables – capability, configuration and runtime state / ✔ 16 counter metadata |
| `Server` / `DefaultHAConfiguration`, `DefaultHEConfiguration` | 22 | Part 11: the server's default historizing configuration (`Stepped`, `MinTimeInterval`, `MaxTimeInterval`, `ExceptionDeviation`, aggregate configuration) and archive state (`StartOfArchive`, `StartOfOnlineArchive`, `MaxCountStoredValues`, …). | ✘ 17 variables |
| `Server` / `Resources` / `ProvisionableDevice` | 11 | Part 21 device onboarding: `IsSingleton` describes the device. | ✘ 1 variable |
| `Server` / `Dictionaries`, `Quantities` | 2 | Entry folders (Part 19 dictionaries, quantities) without value – comparable to `Machines`. Their *content* is server specific. | ✔ |

**Pattern:** core declares the Server object and its well-known *server-describing* children (`ServerCapabilities`,
`ServerStatus`, `Namespaces`, …) dynamic, but leaves later additions to the Server object –
`ServerConfiguration`, `PublishSubscribe`, `RoleSet` roles, historian defaults, `Resources` – in its static ranges.
These are *well-known instances*: same NodeId in every server, but server specific content. DI repeats the pattern
with `MaxInactiveLockTime`, other companion specifications only attach their NamespaceMetadata.

## 3. Static instances outside dynamic structures

The structural check of section 2 does not find server state on static nodes that are *not* below a dynamic node.
Static instance variables (no instance declaration) without a value fixed by the nodeset:

| Namespace | Node | Semantics | Verdict |
|---|---|---|---|
| DI | `Objects/DeviceTopology/OnlineAccess` | *"Hint of whether the Server is currently able to communicate to Devices in the topology."* – runtime state of the server. `DeviceTopology` is a static global entry folder, so the variable is a static, global node. | ✘ server state on a static node |
| core | `Objects/Aliases/LastChange` | Part 17: time of the last change of the alias names of the server. `Aliases` is a static entry folder below `Objects`. | ✘ server state on a static node |
| core | `AllowNulls`, `EngineeringUnits`, `EnumStrings`, `EnumValues`, `InputArguments`, `MaxStringLength`, … (21 standalone property nodes) and `HA Configuration` (with its aggregate configuration) | Prototype nodes defining the standard properties/objects (BrowseName and semantics, Part 3/5/11). They have no parent and are never the property of a real node – servers create their own nodes with these names. | ✔ prototypes |

## 4. Type system nodes: encodings, type dictionaries, dictionary entries

**What they are.** A structured DataType has *DataTypeEncoding* objects ("Default Binary", "Default XML",
"Default JSON", linked by `HasEncoding`). Their NodeIds are written into every encoded ExtensionObject
(`TypeId`) on the wire – sender and receiver must agree on them, so they are **identical in every server by
construction**. The (deprecated, still shipped) *DataTypeDictionary*/*DataTypeDescription* variables describe the
binary/XML schema of the namespace. All of them are part of the type definition, although technically they are
instances (`UAObject`/`UAVariable`) without modelling rule – the fallback rule therefore calls them dynamic.

| Namespace | encoding objects | type dictionaries | data type descriptions | static by |
|---|---|---|---|---|
| core | 483 static | 2 static | 322 static | NamespaceMetadata |
| DI, ISA95-JobControl, Machinery/Result, Pumps, TMC, IA, MachineTool | 129 static | 14 static | 82 static | NamespaceMetadata |
| **PackML** | **12 dynamic** | **2 dynamic** | **12 dynamic** | fallback rule |
| **ISA95** | **8 dynamic** | **2 dynamic** | **8 dynamic** | fallback rule |

Where the NamespaceMetadata decides, they are static – the *node kind* is not the problem, the missing metadata is.
In the global versions of PackML and ISA95 the DataTypes lose their encodings: **12 + 8 `HasEncoding` references**
are dropped, and with a server URI each server would get its own copy of an encoding that is identical everywhere.

**Dictionary entries** behave the same: the 51 IEC 61987 entries of the IRDI dictionary (`IrdiDictionaryEntryType`)
are global concepts – the IRDI is a worldwide identifier – but the IRDI NamespaceMetadata decides nothing, so they
are dynamic and **PADIM loses 57 `HasDictionaryEntry` references** from its (static) types to their semantic
definitions.

## 5. Proposals

1. **Define "static" completely**: same NodeId, attributes, references *and readable values* in every server.
   A static instance with a server specific value is a modelling error. For well-known instances there are three
   options: declare them dynamic (core's NamespaceMetadata ranges for `ServerConfiguration`, `PublishSubscribe`,
   role mappings, historian defaults; DI for `MaxInactiveLockTime` and `OnlineAccess`), split the static identity
   from a dynamic value node, or mark server specific properties explicitly.
2. **Extend the fallback rule** for the type system: targets of `HasEncoding`, DataTypeDictionary/Description/System
   nodes and dictionary entries are static. Entry folders organized directly by `Objects` (like `PackMLObjects`)
   are candidates as well.
3. **Validate NamespaceMetadata**: warn about metadata that decides nothing (PackML, IRDI, examples), missing
   metadata (ISA95) and implausible values (ISA95-JobControl pattern `"0"`); a specification whose own
   NamespaceMetadata object is dynamic has no metadata in its global version.
4. **Detect automatically** with SHACL ([`static_state_shapes.ttl`](static_state_shapes.ttl)): structural (static
   variable below a dynamic node, shape SH4) and value based (static, readable instance variable without a specified value,
   shape SH1) – the two views are complementary (sections 2 and 3).
5. **Composition**: static nodes inside server structures get one parent per server; with server state they get
   conflicting values. Until the specifications are fixed, consumers should treat the ✘ nodes above as server
   specific.

## Reproduce

```bash
cd semantic-model/opcua/docs/static-dynamic-analysis
python3 build_exports.py /tmp/exports            # full nodeset2owl exports (with --serverUri) of all 20 nodesets
python3 analyze.py /tmp/exports report.md        # data report: dynamic subtrees, static nodes below dynamic
                                                 # nodes with categories, static instances without value,
                                                 # type system nodes
```
