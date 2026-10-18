# Core: nodes reclassified by the instance-with-variables heuristic

For review. Core nodeset `Opc.Ua.NodeSet2.xml`, UA-Nodeset UA-1.05.03-2023-12-15, namespace
`http://opcfoundation.org/UA/` (all NodeIds below are namespace 0). Generated from
`nodeset2owl.py --classification-report` (see [heuristic-overrides.md](heuristic-overrides.md) for all
companion specifications).

## Summary

- **232 nodes** change their classification, all **static → dynamic**. Core's NamespaceMetadata
  (36 static numeric ranges) classifies them static, the heuristic classifies them dynamic. The heuristic
  never makes a node static.
- They belong to **46 instances with Variables**; every instance is reclassified together with its
  Variables (column *Variables*). An instance whose Variables are themselves instances with Variables
  (PubSub `Diagnostics`, `Counters`, `LiveValues`) is listed once per level: 12
  Variables appear twice, as Variable of their parent and in their own row.
- **All but 7** are reachable from `Root/Objects`: below the Server object (`i=2253`) or the `Aliases` folder.
  The 7 others are `HA Configuration` (`i=11202`) and its children, which are not reachable at all (see
  below).

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
less instances are definitions and keep the classification of the NamespaceMetadata/default rule (static here).
In core this removes the 7 `HA Configuration` nodes from the list; the other unreferenced definitions have no
Variables and are not affected anyway.

## The reclassified instances

| Instance | BrowseName | TypeDefinition | Browse path | # Variables | Variables made dynamic |
|---|---|---|---|---|---|
| `i=11202` | HA Configuration | `i=2318` | — (not reachable from Root) | 1 | `i=11208` Stepped |
| `i=11203` | AggregateConfiguration | `i=11187` | — (not reachable from Root) | 4 | `i=11204` TreatUncertainAsBad, `i=11205` PercentDataBad, `i=11206` PercentDataGood, `i=11207` UseSlopedExtrapolation |
| `i=12637` | ServerConfiguration | `i=12581` | Root/Objects/Server/ServerConfiguration | 8 | `i=12639` SupportedPrivateKeyFormats, `i=12640` MaxTrustListSize, `i=12641` MulticastDnsEnabled, `i=12710` ServerCapabilities, `i=23597` HasSecureElement, `i=25706` ApplicationUri, `i=25707` ApplicationType, `i=25725` ProductUri |
| `i=12642` | TrustList | `i=12522` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultApplicationGroup/TrustList | 5 | `i=12643` Size, `i=12646` OpenCount, `i=12662` LastUpdateTime, `i=14157` Writable, `i=14158` UserWritable |
| `i=14088` | DefaultHttpsGroup | `i=12555` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultHttpsGroup | 1 | `i=14121` CertificateTypes |
| `i=14089` | TrustList | `i=12522` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultHttpsGroup/TrustList | 5 | `i=14090` Size, `i=14091` Writable, `i=14092` UserWritable, `i=14093` OpenCount, `i=14110` LastUpdateTime |
| `i=14122` | DefaultUserTokenGroup | `i=12555` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultUserTokenGroup | 1 | `i=14155` CertificateTypes |
| `i=14123` | TrustList | `i=12522` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultUserTokenGroup/TrustList | 5 | `i=14124` Size, `i=14125` Writable, `i=14126` UserWritable, `i=14127` OpenCount, `i=14144` LastUpdateTime |
| `i=14156` | DefaultApplicationGroup | `i=12555` | Root/Objects/Server/ServerConfiguration/CertificateGroups/DefaultApplicationGroup | 1 | `i=14161` CertificateTypes |
| `i=14443` | PublishSubscribe | `i=14416` | Root/Objects/Server/PublishSubscribe | 5 | `i=17481` SupportedTransportProfiles, `i=25480` DefaultDatagramPublisherId, `i=25481` ConfigurationVersion, `i=32403` DefaultSecurityKeyServices, `i=32404` ConfigurationProperties |
| `i=15644` | Anonymous | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/Anonymous | 5 | `i=15412` ApplicationsExclude, `i=15413` EndpointsExclude, `i=16192` Identities, `i=16193` Applications, `i=16194` Endpoints |
| `i=15656` | AuthenticatedUser | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/AuthenticatedUser | 6 | `i=15414` ApplicationsExclude, `i=15415` EndpointsExclude, `i=16203` Identities, `i=16204` Applications, `i=16205` Endpoints, `i=24141` CustomConfiguration |
| `i=15668` | Observer | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/Observer | 6 | `i=15416` ApplicationsExclude, `i=15417` EndpointsExclude, `i=16214` Identities, `i=16215` Applications, `i=16216` Endpoints, `i=24142` CustomConfiguration |
| `i=15680` | Operator | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/Operator | 6 | `i=15418` ApplicationsExclude, `i=15423` EndpointsExclude, `i=16225` Identities, `i=16226` Applications, `i=16227` Endpoints, `i=24143` CustomConfiguration |
| `i=15692` | Supervisor | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/Supervisor | 6 | `i=15426` ApplicationsExclude, `i=15427` EndpointsExclude, `i=16247` Identities, `i=16248` Applications, `i=16249` Endpoints, `i=24145` CustomConfiguration |
| `i=15704` | SecurityAdmin | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/SecurityAdmin | 6 | `i=15430` ApplicationsExclude, `i=15527` EndpointsExclude, `i=16258` Identities, `i=16259` Applications, `i=16260` Endpoints, `i=24147` CustomConfiguration |
| `i=15716` | ConfigureAdmin | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/ConfigureAdmin | 6 | `i=15428` ApplicationsExclude, `i=15429` EndpointsExclude, `i=16269` Identities, `i=16270` Applications, `i=16271` Endpoints, `i=24146` CustomConfiguration |
| `i=15957` | http://opcfoundation.org/UA/ | `i=11616` | Root/Objects/Server/Namespaces/http://opcfoundation.org/UA/ | 11 | `i=15958` NamespaceUri, `i=15959` NamespaceVersion, `i=15960` NamespacePublicationDate, `i=15961` IsNamespaceSubset, `i=15962` StaticNodeIdTypes, `i=15963` StaticNumericNodeIdRange, `i=15964` StaticStringNodeIdPattern, `i=16134` DefaultRolePermissions, `i=16135` DefaultUserRolePermissions, `i=16136` DefaultAccessRestrictions, `i=32408` ModelVersion |
| `i=16036` | Engineer | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/Engineer | 6 | `i=15424` ApplicationsExclude, `i=15425` EndpointsExclude, `i=16236` Identities, `i=16237` Applications, `i=16238` Endpoints, `i=24144` CustomConfiguration |
| `i=17405` | Status | `i=14643` | Root/Objects/Server/PublishSubscribe/Status | 1 | `i=17406` State |
| `i=17409` | Diagnostics | `i=19732` | Root/Objects/Server/PublishSubscribe/Diagnostics | 4 | `i=17410` DiagnosticsLevel, `i=17411` TotalInformation, `i=17416` TotalError, `i=17422` SubError |
| `i=17411` | TotalInformation | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/TotalInformation | 3 | `i=17412` Active, `i=17413` Classification, `i=17414` DiagnosticsLevel |
| `i=17416` | TotalError | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/TotalError | 3 | `i=17417` Active, `i=17418` Classification, `i=17419` DiagnosticsLevel |
| `i=17423` | Counters | `i=58` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters | 6 | `i=17424` StateError, `i=17431` StateOperationalByMethod, `i=17436` StateOperationalByParent, `i=17441` StateOperationalFromError, `i=17446` StatePausedByParent, `i=17451` StateDisabledByMethod |
| `i=17424` | StateError | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StateError | 3 | `i=17425` Active, `i=17426` Classification, `i=17429` DiagnosticsLevel |
| `i=17431` | StateOperationalByMethod | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StateOperationalByMethod | 3 | `i=17432` Active, `i=17433` Classification, `i=17434` DiagnosticsLevel |
| `i=17436` | StateOperationalByParent | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StateOperationalByParent | 3 | `i=17437` Active, `i=17438` Classification, `i=17439` DiagnosticsLevel |
| `i=17441` | StateOperationalFromError | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StateOperationalFromError | 3 | `i=17442` Active, `i=17443` Classification, `i=17444` DiagnosticsLevel |
| `i=17446` | StatePausedByParent | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StatePausedByParent | 3 | `i=17447` Active, `i=17448` Classification, `i=17449` DiagnosticsLevel |
| `i=17451` | StateDisabledByMethod | `i=19725` | Root/Objects/Server/PublishSubscribe/Diagnostics/Counters/StateDisabledByMethod | 3 | `i=17452` Active, `i=17453` Classification, `i=17454` DiagnosticsLevel |
| `i=17457` | LiveValues | `i=58` | Root/Objects/Server/PublishSubscribe/Diagnostics/LiveValues | 4 | `i=17458` ConfiguredDataSetWriters, `i=17460` ConfiguredDataSetReaders, `i=17462` OperationalDataSetWriters, `i=17464` OperationalDataSetReaders |
| `i=17458` | ConfiguredDataSetWriters | `i=63` | Root/Objects/Server/PublishSubscribe/Diagnostics/LiveValues/ConfiguredDataSetWriters | 1 | `i=17459` DiagnosticsLevel |
| `i=17460` | ConfiguredDataSetReaders | `i=63` | Root/Objects/Server/PublishSubscribe/Diagnostics/LiveValues/ConfiguredDataSetReaders | 1 | `i=17461` DiagnosticsLevel |
| `i=17462` | OperationalDataSetWriters | `i=63` | Root/Objects/Server/PublishSubscribe/Diagnostics/LiveValues/OperationalDataSetWriters | 1 | `i=17463` DiagnosticsLevel |
| `i=17464` | OperationalDataSetReaders | `i=63` | Root/Objects/Server/PublishSubscribe/Diagnostics/LiveValues/OperationalDataSetReaders | 1 | `i=17466` DiagnosticsLevel |
| `i=23470` | Aliases | `i=23456` | Root/Objects/Aliases | 1 | `i=32852` LastChange |
| `i=23678` | PubSubCapablities | `i=23832` | Root/Objects/Server/PublishSubscribe/PubSubCapablities | 16 | `i=23679` MaxPubSubConnections, `i=23680` MaxWriterGroups, `i=23681` MaxReaderGroups, `i=23682` MaxDataSetWriters, `i=23683` MaxDataSetReaders, `i=23684` MaxFieldsPerDataSet, `i=32398` MaxDataSetWritersPerGroup, `i=32399` MaxNetworkMessageSizeDatagram, `i=32400` MaxNetworkMessageSizeBroker, `i=32401` SupportSecurityKeyPull, `i=32402` SupportSecurityKeyPush, `i=32839` MaxSecurityGroups, `i=32840` MaxPushTargets, `i=32841` MaxPublishedDataSets, `i=32842` MaxStandaloneSubscribedDataSets, `i=32843` SupportSecurityKeyServer |
| `i=24290` | UserManagement | `i=24264` | Root/Objects/Server/ServerConfiguration/UserManagement | 4 | `i=24291` PasswordRestrictions, `i=24301` Users, `i=24302` PasswordLength, `i=24303` PasswordOptions |
| `i=25451` | PubSubConfiguration | `i=25482` | Root/Objects/Server/PublishSubscribe/PubSubConfiguration | 4 | `i=25452` Size, `i=25453` Writable, `i=25454` UserWritable, `i=25455` OpenCount |
| `i=25565` | SecurityKeyServerAdmin | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/SecurityKeyServerAdmin | 6 | `i=25566` Identities, `i=25567` ApplicationsExclude, `i=25568` Applications, `i=25569` EndpointsExclude, `i=25570` Endpoints, `i=25571` CustomConfiguration |
| `i=25584` | SecurityKeyServerPush | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/SecurityKeyServerPush | 6 | `i=25585` Identities, `i=25586` ApplicationsExclude, `i=25587` Applications, `i=25588` EndpointsExclude, `i=25589` Endpoints, `i=25590` CustomConfiguration |
| `i=25603` | SecurityKeyServerAccess | `i=15620` | Root/Objects/Server/ServerCapabilities/RoleSet/SecurityKeyServerAccess | 6 | `i=25604` Identities, `i=25605` ApplicationsExclude, `i=25606` Applications, `i=25607` EndpointsExclude, `i=25608` Endpoints, `i=25609` CustomConfiguration |
| `i=29878` | ProvisionableDevice | `i=26871` | Root/Objects/Server/Resources/ProvisionableDevice | 1 | `i=29879` IsSingleton |
| `i=32637` | DefaultHAConfiguration | `i=2318` | Root/Objects/Server/DefaultHAConfiguration | 11 | `i=32644` Stepped, `i=32645` Definition, `i=32646` MaxTimeInterval, `i=32647` MinTimeInterval, `i=32648` ExceptionDeviation, `i=32649` ExceptionDeviationFormat, `i=32650` StartOfArchive, `i=32656` StartOfOnlineArchive, `i=32682` ServerTimestampSupported, `i=32752` MaxTimeStoredValues, `i=32753` MaxCountStoredValues |
| `i=32638` | AggregateConfiguration | `i=11187` | Root/Objects/Server/DefaultHAConfiguration/AggregateConfiguration | 4 | `i=32639` TreatUncertainAsBad, `i=32640` PercentDataBad, `i=32641` PercentDataGood, `i=32642` UseSlopedExtrapolation |
| `i=32754` | DefaultHEConfiguration | `i=32621` | Root/Objects/Server/DefaultHEConfiguration | 2 | `i=32756` StartOfArchive, `i=32757` StartOfOnlineArchive |

## Appendix: core Objects/Variables without parent and incoming reference

66 nodes: `i=3062` Default Binary, `i=3063` Default XML, `i=84` Root, `i=3068` NodeVersion, `i=12170` ViewVersion, `i=3067` Icon, `i=3069` LocalTime, `i=3070` AllowNulls, `i=11433` ValueAsText, `i=11498` MaxStringLength, `i=15002` MaxCharacters, `i=12908` MaxByteStringLength, `i=11512` MaxArrayLength, `i=11513` EngineeringUnits, `i=11432` EnumStrings, `i=3071` EnumValues, `i=12745` OptionSetValues, `i=32750` OptionSetLength, `i=3072` InputArguments, `i=3073` OutputArguments, `i=17605` DefaultInstanceBrowseName, `i=11312` CurrentServerId, `i=11314` ServerUriArray, `i=14415` ServerNetworkGroups, `i=16314` FileSystem, `i=23501` CurrencyUnit, `i=11214` Annotations, `i=11202` HA Configuration, `i=11215` HistoricalEventFilter, `i=2341` Interpolative, `i=2342` Average, `i=2343` TimeAverage, `i=11285` TimeAverage2, `i=2344` Total, `i=11304` Total2, `i=2346` Minimum, `i=2347` Maximum, `i=2348` MinimumActualTime, `i=2349` MaximumActualTime, `i=2350` Range, `i=11286` Minimum2, `i=11287` Maximum2, `i=11305` MinimumActualTime2, `i=11306` MaximumActualTime2, `i=11288` Range2, `i=2351` AnnotationCount, `i=2352` Count, `i=11307` DurationInStateZero, `i=11308` DurationInStateNonZero, `i=2355` NumberOfTransitions, `i=2357` Start, `i=2358` End, `i=2359` Delta, `i=11505` StartBound, `i=11506` EndBound, `i=11507` DeltaBounds, `i=2360` DurationGood, `i=2361` DurationBad, `i=2362` PercentGood, `i=2363` PercentBad, `i=2364` WorstQuality, `i=11292` WorstQuality2, `i=11426` StandardDeviationSample, `i=11427` StandardDeviationPopulation, `i=11428` VarianceSample, `i=11429` VariancePopulation
