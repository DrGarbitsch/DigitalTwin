# Static/dynamic classification: issues per specification owner

Change requests derived from the evaluation of the 20 nodesets of `translate_default_nodesets.make` (UA-Nodeset
UA-1.05.03-2023-12-15). Each item names the nodes (NodeIds in the namespace of the nodeset, `ns=1` unless noted), the
evidence and the requested change. Fixed in the specifications, the corresponding heuristic overrides of nodeset2owl.py
disappear (see [classification-changes.md](classification-changes.md); rules in the
[README](../../README.md#static-and-dynamic-nodes) and [heuristic-outliers.md](heuristic-outliers.md)).

PADIM NodeIds below are in the PADIM namespace (`ns=3` in its nodeset). The common background is the definition of static nodes in OPC 10000-5 §6.3.13 (NamespaceMetadataType):

> Static Nodes are identical for all Attributes in all Servers, including the Value Attribute.

and OPC 11030 §7.11 (UA Modelling Best Practices) for standardized instances which are bound to a server:

> it is important to mark those Nodes in the NamespaceMetadata Object of the Namespace as non-static.

## OPC Foundation – core (`http://opcfoundation.org/UA/`, `Opc.Ua.NodeSet2.xml`)

**C1. Server specific content inside the static ranges.** Core's NamespaceMetadata (`i=15957`,
StaticNumericNodeIdRange `i=15963`, 36 ranges) excludes the Server object and its classic children (ServerStatus,
ServerCapabilities, Namespaces, …), but the later additions to the Server object are inside the static ranges although
their values are server specific. nodeset2owl.py reclassifies 240 core nodes (R1/R2); the instances are:

| Instance | NodeId | Server specific content (examples) |
|---|---|---|
| ServerConfiguration | `i=12637` | `ApplicationUri` (`i=25706`), `ProductUri` (`i=25725`), `ApplicationType` (`i=25707`), `MaxTrustListSize` (`i=12640`) |
| certificate groups and trust lists | `i=14053`, `i=14088`, `i=14089`, `i=14122`, `i=14123`, `i=14156`, `i=12642` | `CertificateTypes`, trust list `Size`, `LastUpdateTime`, `OpenCount` |
| AuthorizationServices, KeyCredentialConfiguration | `i=17732`, `i=18155` | the server's authorization services and credentials |
| UserManagement | `i=24290` | `Users` (`i=24301`), password restrictions |
| RoleSet roles (Anonymous … SecurityKeyServerAccess) | `i=15644`, `i=15656`, `i=15668`, `i=15680`, `i=15692`, `i=15704`, `i=15716`, `i=16036`, `i=25565`, `i=25584`, `i=25603` | `Identities`, `Applications`, `Endpoints` of each role |
| PublishSubscribe | `i=14443` | status, diagnostics (`i=17409`), `PubSubCapablities` (`i=23678`), `SecurityGroups` (`i=15443`), `PublishedDataSets` (`i=17371`), `SubscribedDataSets` (`i=23658`), `KeyPushTargets` (`i=25440`), `PubSubConfiguration` (`i=25451`) |
| historian defaults | `i=32637`, `i=32638`, `i=32754` | `MaxTimeInterval`, `StartOfArchive`, `AggregateFunctions` (`i=32643`), `EventTypes` (`i=32755`) |
| Resources | `i=24226` | `ProvisionableDevice` (`i=29878`) |
| Dictionaries | `i=17594` | the dictionaries this server exposes |
| core's NamespaceMetadata | `i=15957` | `IsNamespaceSubset` (`i=15961`), `DefaultRolePermissions` (`i=16134`), … |
| Aliases | `i=23470` | `LastChange` (`i=32852`) |

Also server specific, but not reclassified because they are only *organized* (not aggregated) by these instances:
`TagVariables` (`i=23479`) and `Topics` (`i=23488`) by `Aliases` (their type AliasNameCategoryType declares
`LastChange`), `Quantities` (`i=32530`) by the Server object, `Communication` (`i=24227`) with `MappingTables`,
`NetworkInterfaces`, `Streams`, `TalkerStreams`, `ListenerStreams` (`i=24228`–`i=24232`) by `Resources`.

*Request:* exclude these subtrees from `StaticNumericNodeIdRange`, as for the classic Server children – or split
identity and value (a static declaration, server specific values on server specific nodes).

**C1a. Missing ParentNodeId.** `Dictionaries` (`i=17594`, HasComponent of the Server object), `AuthorizationServices`
(`i=17732`) and `KeyCredentialConfiguration` (`i=18155`, both HasComponent of ServerConfiguration) and `Resources`
(`i=24226`, HasComponent of the Server object) have no ParentNodeId, unlike the other components of these instances
(e.g. `CertificateGroups` `i=14053` with `ParentNodeId="i=12637"`). nodeset2owl.py derives the coupling to a parent
from the ParentNodeId only (R2), so they stay static although their parents are server specific.
*Request:* add the ParentNodeId (and exclude them from the static ranges, see C1).

**C2. Prototypes exported as nodes.** The nodeset contains 66 Objects/Variables without parent and without any
incoming reference, which define standard BrowseNames or structures rather than nodes of a server, e.g.
`HA Configuration` (`i=11202`, Part 11 §5.2.4) with its children `i=11203`–`i=11208`, `FileSystem` (`i=16314`),
`Default Binary`/`Default XML` (`i=3062`, `i=3063`), `DefaultInstanceBrowseName` (`i=17605`) and the standard Property
prototypes (`AllowNulls` `i=3070`, `EngineeringUnits` `i=11513`, …). They are neither instances, instance declarations
nor types; `HA Configuration` is classified dynamic by its Variables.
*Request:* mark them as prototypes (e.g. `DesignToolOnly`) or express the standard BrowseName via
`DefaultInstanceBrowseName` on the type (e.g. HistoricalDataConfigurationType), instead of exporting them as instances.

**C3. Disconnected redundancy Variables.** `CurrentServerId` (`i=11312`), `ServerUriArray` (`i=11314`) and
`ServerNetworkGroups` (`i=14415`) (SymbolicNames `Server_ServerRedundancy_…`) have no reference to the Server object.
*Request:* add the references (or remove the nodes).

## OPC Foundation / DI WG – Devices (`http://opcfoundation.org/UA/DI/`)

**D1. `MaxInactiveLockTime`** (`i=6387`), a Property of core's ServerCapabilities: DI describes it as *"Server-specific
period of time in milliseconds until the Server will revoke a lock."*, but DI's StaticNumericNodeIdRange
(`1:2147483647`) declares it static.

**D2. `DeviceTopology/OnlineAccess`** (`i=6095`): *"Hint of whether the Server is currently able to communicate to
Devices in the topology."* – runtime state of the server on a static node.

**D3. DI's NamespaceMetadata object** (`i=15001` with its Properties): below core's server specific
`Server/Namespaces`, with server specific values (`IsNamespaceSubset`, `DefaultRolePermissions`, …), but static.

*Request:* exclude `i=6387`, `i=6094`/`i=6095` and the NamespaceMetadata object from the static range.

## All companion specifications with NamespaceMetadata

**A1. The NamespaceMetadata object is declared static.** DEXPI (`i=5001`), IA (`i=5008`), ISA95-JobControl
(`i=5001`), LaserSystems (`i=5105`), Machinery (`i=5001`), Machinery/ProcessValues (`i=5001`), Machinery/Result
(`i=5007`), MachineTool (`i=120`), PADIM (`i=1000`), Pumps (`i=5239`), TMC (`i=5006`) and DI (`i=15001`): the
object is a component of the server specific `Server/Namespaces` (`i=11715`) and its Properties `IsNamespaceSubset`
and the role permissions are server specific. nodeset2owl.py makes 8–14 nodes per specification dynamic (R1).
*Request:* exclude the NamespaceMetadata object and its Properties from the static ranges (guidance in OPC 11030 /
the Companion Specification template).

## PackML (`http://opcfoundation.org/UA/PackML/`)

**P1. Empty NamespaceMetadata.** The NamespaceMetadata object (`i=117`) has `StaticNodeIdTypes` (`i=358`),
`StaticNumericNodeIdRange` (`i=359`) and `StaticStringNodeIdPattern` (`i=360`) without values, so it decides nothing:
the DataType encodings (`i=69`, `i=70`, `i=74`, `i=76`–`i=84`), the type dictionaries (`i=195`–`i=198`) and their
descriptions (`i=180`–`i=191`) are dynamic by the standard default fallback (R5), and the global model loses the `HasEncoding`
links of the PackML DataTypes (nodeset2owl.py makes these 28 nodes static, R4); the entry folder `PackMLObjects`
(`i=72`) stays dynamic.
*Request:* set `StaticNumericNodeIdRange` (e.g. `1:65535`, excluding the NamespaceMetadata object `i=117` and
`i=354`–`i=360`, see A1).

## ISA95 (`http://www.OPCFoundation.org/UA/2013/01/ISA95`, `Opc.ISA95.NodeSet2.xml`)

**I1. No NamespaceMetadata.** The 8 DataType encodings and the type dictionaries with their descriptions (12 nodes) are
dynamic by the standard default fallback (nodeset2owl.py: static by the definition fallback R4).
*Request:* add a NamespaceMetadata object with static ranges.

**I2. ISA95-JobControl** (`http://opcfoundation.org/UA/ISA95-JOBCONTROL`): `StaticStringNodeIdPattern = "0"`, a
regular expression matching only the string id `"0"` – almost certainly unintended (no effect today, all ids are
numeric). *Request:* remove or correct the pattern.

## PADIM / IRDI dictionary (`http://opcfoundation.org/UA/Dictionary/IRDI`, published with PADIM)

**R1. Empty NamespaceMetadata.** The IRDI nodeset's NamespaceMetadata (`i=1000`) has `IsNamespaceSubset` (`i=1001`),
`StaticNodeIdTypes` (`i=1005`), `StaticNumericNodeIdRange` (`i=1006`) and `StaticStringNodeIdPattern` (`i=1007`)
without values: the 51 dictionary entries, global definitions which PADIM refers to (`HasDictionaryEntry`), are
dynamic by the standard default fallback (nodeset2owl.py: static by the definition fallback R4).
*Request:* declare the string ids static (`StaticNodeIdTypes` = String, or a `StaticStringNodeIdPattern` such as
`0112/.*`) and set `IsNamespaceSubset`.

**R2. Referenced entries missing in the nodeset.** PADIM's `EnumDictionaryEntries` (PADIM `i=1161`, a Property of
the Mandatory declaration `SensorType` (`i=1128`) of TemperatureMeasurementVariableType `i=1120`) holds 50 IRDI
NodeIds as value (38 distinct, e.g. `s=0112/2///61987#ABK976#001`) which the IRDI nodeset does not contain (it
contains 51 entries). A static node's
value must be identical in all servers, so these entries must have a global identity, but no nodeset defines them.
*Request:* publish the referenced entries in the IRDI nodeset.

**R3. `HasDictionaryEntry` to a placeholder declaration.** `PADIMType` refers via `HasDictionaryEntry` to core's
`<DictionaryEntryName>` (`i=17590`), the placeholder instance declaration of DictionaryEntryType, instead of a dictionary
entry. *Request:* check the intended target.

## DEXPI (`http://opcfoundation.org/UA/DEXPI/`)

**X1. Instance Variables with a ModellingRule.** `DEXPISupplementaryData` (`i=2122`, organized by Objects) has the
Properties `DEXPISpecificationVersion` (`i=2123`) and `ProteusSchemaVersion` (`i=2124`), both with
`HasModellingRule Optional` (`i=80`), which is only meaningful for instance declarations, and writable
(`AccessLevel="3"`). If the values are fixed by the specification, they are static constants and should not be
writable; if they are server specific, the object should not be in the static range.
*Request:* remove the ModellingRules and clarify static vs. server specific (nodeset2owl.py: dynamic by R1).
