# Core: nodes reclassified by the heuristic rules

For review. Core nodeset `Opc.Ua.NodeSet2.xml`, UA-Nodeset UA-1.05.03-2023-12-15, namespace
`http://opcfoundation.org/UA/` (all NodeIds below are namespace 0). The complete list of the changed nodes, grouped by
rule and area, is in [classification-changes.md](classification-changes.md#core); the rules are described in the
[README](../../README.md#static-and-dynamic-nodes).

## Summary

- **516 nodes** change their classification, all **static → dynamic**. Core's NamespaceMetadata (R3, 36 static
  numeric ranges) classifies them static:
  - **232 by R1** (instance-with-Variables override): 46 instances with their Variables – ServerConfiguration and the
    certificate management, the RoleSet roles, PubSub, the historian defaults, core's NamespaceMetadata,
    UserManagement, `Aliases`, `ProvisionableDevice`.
  - **284 by R2** (ParentNodeId override): the nodes whose ParentNodeId is dynamic – 8 folders
    (`CertificateGroups`, `SecurityGroups`, `PublishedDataSets`, `SubscribedDataSets`, `DataSetClasses`,
    `KeyPushTargets`, `AggregateFunctions`, `EventTypes`), 126 Methods of the dynamic instances (e.g. `AddIdentity`,
    `RemoveEndpoint` of the 11 roles, `Open`, `CloseAndUpdate` of the trust lists) and their 150
    `InputArguments`/`OutputArguments`. Core's NamespaceMetadata treats the Methods of the Server object (e.g.
    `GetMonitoredItems` `i=11492` with its `InputArguments` `i=11493`) the same way.
  - Not reclassified: the folders `Dictionaries` (`i=17594`), `AuthorizationServices` (`i=17732`),
    `KeyCredentialConfiguration` (`i=18155`) and `Resources` (`i=24226`) are components (HasComponent) of dynamic
    instances, but have no ParentNodeId, so R3 decides (static). Folders which are only organized by dynamic
    instances (`TagVariables`, `Topics`, `Quantities`, `Communication` and below it) stay static: Organizes does not
    influence the classification.
- The fallbacks R4 and R5 change nothing in core: R3 decides every core node (and declares core's ModellingRules, encodings and type
  dictionaries static anyway).
- **All but 7** are reachable from `Root/Objects`: below the Server object (`i=2253`) or the `Aliases` folder. The 7
  others are `HA Configuration` (`i=11202`) and its children, which are not reachable at all (see below).

## Finding: `HA Configuration` (`i=11202`) is a prototype, not an instance

```xml
<UAObject NodeId="i=11202" BrowseName="HA Configuration" SymbolicName="HAConfiguration">
  <Documentation>https://reference.opcfoundation.org/v105/Core/docs/Part11/5.2.4</Documentation>
  <References>
    <Reference ReferenceType="HasComponent">i=11203</Reference>   <!-- AggregateConfiguration -->
    <Reference ReferenceType="HasProperty">i=11208</Reference>    <!-- Stepped -->
    <Reference ReferenceType="HasTypeDefinition">i=2318</Reference> <!-- HistoricalDataConfigurationType -->
  </References>
</UAObject>
```

- **No parent, no incoming reference.** The core nodeset contains no `ParentNodeId` for it and no node
  references it; it is not reachable from `Root` (nor from `Objects`).
- **What Part 11 says (§5.2.4 Historical Data Configuration Object):** "If a *HistoricalDataNode* has
  configuration defined then one instance shall have a *BrowseName* of 'HA Configuration'" and "All historical
  configuration *Objects* shall be referenced using the *HasHistoricalConfiguration* *ReferenceType*." So the
  real HA Configuration Objects exist once per historizing Variable of a server, with NodeIds the server
  assigns, referenced from that Variable. They are server specific (dynamic) – but they are *not* `i=11202`.
- **So `i=11202` is the specification's prototype** of these Objects: it fixes the standard BrowseName and the
  structure (it is the Object defined in the table of §5.2.4). It is not a node of any server's AddressSpace.
- **It is not alone.** The core nodeset contains 66 Objects/Variables without parent and without
  any incoming reference (appendix), e.g. the standard Property prototypes (`AllowNulls` `i=3070`,
  `EngineeringUnits` `i=11513`, `InputArguments` `i=3072`, …), all AggregateFunction definitions
  (`Average` `i=2342`, …), `HistoricalEventFilter` (`i=11215`), `Annotations` (`i=11214`), `CurrencyUnit`
  (`i=23501`), `FileSystem` (`i=16314`), `DefaultInstanceBrowseName` (`i=17605`), and the three disconnected
  `Server_ServerRedundancy_*` Variables (`i=11312`, `i=11314`, `i=14415`).

**Is it standard compliant?** A NodeSet2 file describes an information model, not the AddressSpace of a server,
and the core nodeset uses unreferenced nodes deliberately to define standard BrowseNames, properties and aggregate
functions. I found no rule in Part 3/5/6 that every node of a NodeSet must be reachable from Root (I did not find
one for servers either, and did not verify it exhaustively). So the node is most likely compliant as a
*definition*, but it is neither a static global instance nor a dynamic server instance.

**Consequence for the heuristic:** classifying the prototype as dynamic is wrong – with a server URI it would
become `svu=<server>;i=11202`, a node which does not exist in that server. Proposal: apply the heuristic only to
instances which are part of the AddressSpace (reachable via hierarchical references, i.e. with a parent); root-
less instances are definitions and keep the classification of R3 (static here).
In core this removes the 7 `HA Configuration` nodes from the list; the other unreferenced definitions have no
Variables and are not affected anyway. Not implemented.

## Appendix: core Objects/Variables without parent and incoming reference

66 nodes: `i=3062` Default Binary, `i=3063` Default XML, `i=84` Root, `i=3068` NodeVersion, `i=12170` ViewVersion, `i=3067` Icon, `i=3069` LocalTime, `i=3070` AllowNulls, `i=11433` ValueAsText, `i=11498` MaxStringLength, `i=15002` MaxCharacters, `i=12908` MaxByteStringLength, `i=11512` MaxArrayLength, `i=11513` EngineeringUnits, `i=11432` EnumStrings, `i=3071` EnumValues, `i=12745` OptionSetValues, `i=32750` OptionSetLength, `i=3072` InputArguments, `i=3073` OutputArguments, `i=17605` DefaultInstanceBrowseName, `i=11312` CurrentServerId, `i=11314` ServerUriArray, `i=14415` ServerNetworkGroups, `i=16314` FileSystem, `i=23501` CurrencyUnit, `i=11214` Annotations, `i=11202` HA Configuration, `i=11215` HistoricalEventFilter, `i=2341` Interpolative, `i=2342` Average, `i=2343` TimeAverage, `i=11285` TimeAverage2, `i=2344` Total, `i=11304` Total2, `i=2346` Minimum, `i=2347` Maximum, `i=2348` MinimumActualTime, `i=2349` MaximumActualTime, `i=2350` Range, `i=11286` Minimum2, `i=11287` Maximum2, `i=11305` MinimumActualTime2, `i=11306` MaximumActualTime2, `i=11288` Range2, `i=2351` AnnotationCount, `i=2352` Count, `i=11307` DurationInStateZero, `i=11308` DurationInStateNonZero, `i=2355` NumberOfTransitions, `i=2357` Start, `i=2358` End, `i=2359` Delta, `i=11505` StartBound, `i=11506` EndBound, `i=11507` DeltaBounds, `i=2360` DurationGood, `i=2361` DurationBad, `i=2362` PercentGood, `i=2363` PercentBad, `i=2364` WorstQuality, `i=11292` WorstQuality2, `i=11426` StandardDeviationSample, `i=11427` StandardDeviationPopulation, `i=11428` VarianceSample, `i=11429` VariancePopulation
