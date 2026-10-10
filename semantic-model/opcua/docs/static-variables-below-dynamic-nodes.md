# Static variables below dynamic nodes ("delinquents")

Static OPC UA nodes are identical in every server and get one global IRI (no `svu`). A static Variable below a dynamic (server specific) node is one global node inside server specific structure. If its value is server state, servers sharing the IRI contradict each other. This is the candidate list; each entry still has to be checked against the standard.

**How it was produced** (prototype, branch `nodeset2owl-identification`):

- Classification: NamespaceMetadata (`StaticNodeIdTypes`, `StaticNumericNodeIdRange`, `StaticStringNodeIdPattern`), otherwise fallback rule (types and instance declarations static, other instances dynamic).
- Core and DI (UA-Nodeset `UA-1.05.03-2023-12-15`): SHACL shape `uaq:StaticVariableUnderDynamic` (R4 in `static_state_shapes.ttl`) on the nodeset2owl exports with `--serverUri`; a static Variable with a dynamic node anywhere above it (HasComponent, HasProperty, HasOrderedComponent, HasAddIn, Organizes).
- Other companion specifications: same criterion evaluated on the nodeset XML.
- **Access**: no nodeset states an `AccessLevel` for these variables, so all are read-only by the UANodeSet default; whether they are writable in a server cannot be derived from the nodesets.
- **Value**: whether the nodeset defines a value (`value`) or not (`-`).

## Summary

| Group | Count | Namespaces | Assessment |
|---|---|---|---|
| [Method arguments](#method-arguments) | 148 | core | Input/OutputArguments of methods: constant method signatures. |
| [NamespaceMetadata permissions](#namespacemetadata-permissions) | 6 | DI, core | Default role permissions / access restrictions of a namespace: server security configuration on a static node. |
| [NamespaceMetadata constants](#namespacemetadata-constants) | 92 | DEXPI, DI, IA, ISA95-JOBCONTROL, LaserSystems, MachineTool, Machinery, Machinery/ProcessValues, Machinery/Result, PADIM, Pumps, TMC/v2, core | Namespace description (URI, version, date, static NodeId rules): constant. |
| [Server capabilities](#server-capabilities) | 1 | DI | Server specific limits/settings added by a companion specification. |
| [Role configuration](#role-configuration) | 65 | core | Well-known roles: identity/application/endpoint mappings are configured per server. |
| [Certificates / TrustList](#certificates--trustlist) | 30 | core | Certificate groups and TrustList file: server security configuration and state. |
| [PubSub](#pubsub) | 68 | core | PublishSubscribe configuration, capabilities, status and diagnostics: server configuration and state. |
| [Historian defaults](#historian-defaults) | 17 | core | Default historical data/event and aggregate configuration: server configuration. |
| [Other](#other) | 1 | core |  |
| **Total** | **428** | | |

## Method arguments

Input/OutputArguments of methods: constant method signatures.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | RoleSet (`i=15606`) | Anonymous / AddApplication / InputArguments | `i=16196` | value | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / AddEndpoint / InputArguments | `i=16200` | value | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / AddIdentity / InputArguments | `i=15649` | value | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / RemoveApplication / InputArguments | `i=16198` | value | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / RemoveEndpoint / InputArguments | `i=16202` | value | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / RemoveIdentity / InputArguments | `i=15651` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / AddApplication / InputArguments | `i=16207` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / AddEndpoint / InputArguments | `i=16211` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / AddIdentity / InputArguments | `i=15661` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / RemoveApplication / InputArguments | `i=16209` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / RemoveEndpoint / InputArguments | `i=16213` | value | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / RemoveIdentity / InputArguments | `i=15663` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / AddApplication / InputArguments | `i=16273` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / AddEndpoint / InputArguments | `i=16277` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / AddIdentity / InputArguments | `i=15721` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / RemoveApplication / InputArguments | `i=16275` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / RemoveEndpoint / InputArguments | `i=16279` | value | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / RemoveIdentity / InputArguments | `i=15723` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / AddApplication / InputArguments | `i=16240` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / AddEndpoint / InputArguments | `i=16244` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / AddIdentity / InputArguments | `i=16042` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / RemoveApplication / InputArguments | `i=16242` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / RemoveEndpoint / InputArguments | `i=16246` | value | read (default) |
| core | RoleSet (`i=15606`) | Engineer / RemoveIdentity / InputArguments | `i=16044` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / AddApplication / InputArguments | `i=16218` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / AddEndpoint / InputArguments | `i=16222` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / AddIdentity / InputArguments | `i=15673` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / RemoveApplication / InputArguments | `i=16220` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / RemoveEndpoint / InputArguments | `i=16224` | value | read (default) |
| core | RoleSet (`i=15606`) | Observer / RemoveIdentity / InputArguments | `i=15675` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / AddApplication / InputArguments | `i=16229` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / AddEndpoint / InputArguments | `i=16233` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / AddIdentity / InputArguments | `i=15685` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / RemoveApplication / InputArguments | `i=16231` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / RemoveEndpoint / InputArguments | `i=16235` | value | read (default) |
| core | RoleSet (`i=15606`) | Operator / RemoveIdentity / InputArguments | `i=15687` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / AddApplication / InputArguments | `i=16262` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / AddEndpoint / InputArguments | `i=16266` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / AddIdentity / InputArguments | `i=15709` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / RemoveApplication / InputArguments | `i=16264` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / RemoveEndpoint / InputArguments | `i=16268` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / RemoveIdentity / InputArguments | `i=15711` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / AddApplication / InputArguments | `i=25615` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / AddEndpoint / InputArguments | `i=25619` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / AddIdentity / InputArguments | `i=25611` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / RemoveApplication / InputArguments | `i=25617` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / RemoveEndpoint / InputArguments | `i=25621` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / RemoveIdentity / InputArguments | `i=25613` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / AddApplication / InputArguments | `i=25577` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / AddEndpoint / InputArguments | `i=25581` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / AddIdentity / InputArguments | `i=25573` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / RemoveApplication / InputArguments | `i=25579` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / RemoveEndpoint / InputArguments | `i=25583` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / RemoveIdentity / InputArguments | `i=25575` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / AddApplication / InputArguments | `i=25596` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / AddEndpoint / InputArguments | `i=25600` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / AddIdentity / InputArguments | `i=25592` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / RemoveApplication / InputArguments | `i=25598` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / RemoveEndpoint / InputArguments | `i=25602` | value | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / RemoveIdentity / InputArguments | `i=25594` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / AddApplication / InputArguments | `i=16251` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / AddEndpoint / InputArguments | `i=16255` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / AddIdentity / InputArguments | `i=15697` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / RemoveApplication / InputArguments | `i=16253` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / RemoveEndpoint / InputArguments | `i=16257` | value | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / RemoveIdentity / InputArguments | `i=15699` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / AddConnection / InputArguments | `i=17367` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / AddConnection / OutputArguments | `i=17368` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / GetSecurityGroup / InputArguments | `i=15441` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / GetSecurityGroup / OutputArguments | `i=15442` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / GetSecurityKeys / InputArguments | `i=15216` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / GetSecurityKeys / OutputArguments | `i=15217` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / KeyPushTargets / AddPushTarget / InputArguments | `i=25442` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / KeyPushTargets / AddPushTarget / OutputArguments | `i=25443` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / KeyPushTargets / RemovePushTarget / InputArguments | `i=25445` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Close / InputArguments | `i=25463` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / CloseAndUpdate / InputArguments | `i=25478` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / CloseAndUpdate / OutputArguments | `i=25479` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / GetPosition / InputArguments | `i=25470` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / GetPosition / OutputArguments | `i=25471` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Open / InputArguments | `i=25460` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Open / OutputArguments | `i=25461` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Read / InputArguments | `i=25465` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Read / OutputArguments | `i=25466` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / ReserveIds / InputArguments | `i=25475` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / ReserveIds / OutputArguments | `i=25476` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / SetPosition / InputArguments | `i=25473` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Write / InputArguments | `i=25468` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / RemoveConnection / InputArguments | `i=17370` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / SecurityGroups / AddSecurityGroup / InputArguments | `i=15445` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / SecurityGroups / AddSecurityGroup / OutputArguments | `i=15446` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / SecurityGroups / RemoveSecurityGroup / InputArguments | `i=15448` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / SetSecurityKeys / InputArguments | `i=17365` | value | read (default) |
| core | Server (`i=2253`) | Resources / ProvisionableDevice / RequestTickets / OutputArguments | `i=29881` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / AddCertificate / InputArguments | `i=12669` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Close / InputArguments | `i=12651` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / CloseAndUpdate / InputArguments | `i=14160` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / CloseAndUpdate / OutputArguments | `i=12667` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / GetPosition / InputArguments | `i=12658` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / GetPosition / OutputArguments | `i=12659` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Open / InputArguments | `i=12648` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Open / OutputArguments | `i=12649` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / OpenWithMasks / InputArguments | `i=12664` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / OpenWithMasks / OutputArguments | `i=12665` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Read / InputArguments | `i=12653` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Read / OutputArguments | `i=12654` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / RemoveCertificate / InputArguments | `i=12671` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / SetPosition / InputArguments | `i=12661` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Write / InputArguments | `i=12656` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / AddCertificate / InputArguments | `i=14118` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Close / InputArguments | `i=14099` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / CloseAndUpdate / InputArguments | `i=14115` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / CloseAndUpdate / OutputArguments | `i=14116` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / GetPosition / InputArguments | `i=14106` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / GetPosition / OutputArguments | `i=14107` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Open / InputArguments | `i=14096` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Open / OutputArguments | `i=14097` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / OpenWithMasks / InputArguments | `i=14112` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / OpenWithMasks / OutputArguments | `i=14113` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Read / InputArguments | `i=14101` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Read / OutputArguments | `i=14102` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / RemoveCertificate / InputArguments | `i=14120` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / SetPosition / InputArguments | `i=14109` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Write / InputArguments | `i=14104` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / AddCertificate / InputArguments | `i=14152` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Close / InputArguments | `i=14133` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / CloseAndUpdate / InputArguments | `i=14149` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / CloseAndUpdate / OutputArguments | `i=14150` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / GetPosition / InputArguments | `i=14140` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / GetPosition / OutputArguments | `i=14141` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Open / InputArguments | `i=14130` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Open / OutputArguments | `i=14131` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / OpenWithMasks / InputArguments | `i=14146` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / OpenWithMasks / OutputArguments | `i=14147` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Read / InputArguments | `i=14135` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Read / OutputArguments | `i=14136` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / RemoveCertificate / InputArguments | `i=14154` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / SetPosition / InputArguments | `i=14143` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Write / InputArguments | `i=14138` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CreateSigningRequest / InputArguments | `i=12738` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CreateSigningRequest / OutputArguments | `i=12739` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / GetRejectedList / OutputArguments | `i=12778` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UpdateCertificate / InputArguments | `i=13738` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UpdateCertificate / OutputArguments | `i=13739` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / AddUser / InputArguments | `i=24305` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / ChangePassword / InputArguments | `i=24311` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / ModifyUser / InputArguments | `i=24307` | value | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / RemoveUser / InputArguments | `i=24309` | value | read (default) |

## NamespaceMetadata permissions

Default role permissions / access restrictions of a namespace: server security configuration on a static node.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / DefaultAccessRestrictions | `i=16136` | - | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / DefaultRolePermissions | `i=16134` | - | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / DefaultUserRolePermissions | `i=16135` | - | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / DefaultAccessRestrictions | `i=15033` | - | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / DefaultRolePermissions | `i=15031` | - | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / DefaultUserRolePermissions | `i=15032` | - | read (default) |

## NamespaceMetadata constants

Namespace description (URI, version, date, static NodeId rules): constant.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / IsNamespaceSubset | `i=15961` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / ModelVersion | `i=32408` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / NamespacePublicationDate | `i=15960` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / NamespaceUri | `i=15958` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / NamespaceVersion | `i=15959` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / StaticNodeIdTypes | `i=15962` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / StaticNumericNodeIdRange | `i=15963` | value | read (default) |
| core | Namespaces (`i=11715`) | http://opcfoundation.org/UA/ / StaticStringNodeIdPattern | `i=15964` | - | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / IsNamespaceSubset | `i=6001` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / NamespacePublicationDate | `i=6002` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / NamespaceUri | `i=6003` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / NamespaceVersion | `i=6004` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6005` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6006` | value | read (default) |
| DEXPI | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/DEXPI/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6007` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / IsNamespaceSubset | `i=15005` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / NamespacePublicationDate | `i=15004` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / NamespaceUri | `i=15002` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / NamespaceVersion | `i=15003` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / StaticNodeIdTypes | `i=15006` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / StaticNumericNodeIdRange | `i=15007` | value | read (default) |
| DI | Namespaces (`i=11715`) | http://opcfoundation.org/UA/DI/ / StaticStringNodeIdPattern | `i=15008` | - | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / IsNamespaceSubset | `i=6039` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / NamespacePublicationDate | `i=6040` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / NamespaceUri | `i=6041` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / NamespaceVersion | `i=6042` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6043` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6044` | value | read (default) |
| IA | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/IA/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6045` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / IsNamespaceSubset | `i=6023` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / NamespacePublicationDate | `i=6024` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / NamespaceUri | `i=6025` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / NamespaceVersion | `i=6026` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / StaticNodeIdTypes | `i=6027` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6028` | value | read (default) |
| ISA95-JOBCONTROL | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/ISA95-JOBCONTROL> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6029` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / IsNamespaceSubset | `i=6156` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / NamespacePublicationDate | `i=6157` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / NamespaceUri | `i=6170` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / NamespaceVersion | `i=6171` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6172` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6173` | value | read (default) |
| LaserSystems | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/LaserSystems/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6174` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / IsNamespaceSubset | `i=396` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / NamespacePublicationDate | `i=397` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / NamespaceUri | `i=398` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / NamespaceVersion | `i=399` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / StaticNodeIdTypes | `i=400` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=406` | value | read (default) |
| MachineTool | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/MachineTool/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=407` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / IsNamespaceSubset | `i=6031` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / NamespacePublicationDate | `i=6032` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / NamespaceUri | `i=6033` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / NamespaceVersion | `i=6034` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6035` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6036` | value | read (default) |
| Machinery | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6037` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / IsNamespaceSubset | `i=6001` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / NamespacePublicationDate | `i=6002` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / NamespaceUri | `i=6003` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / NamespaceVersion | `i=6004` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6005` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6006` | value | read (default) |
| Machinery/ProcessValues | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/ProcessValues/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6007` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / IsNamespaceSubset | `i=6002` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / NamespacePublicationDate | `i=6003` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / NamespaceUri | `i=6004` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / NamespaceVersion | `i=6005` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6006` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6007` | value | read (default) |
| Machinery/Result | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Machinery/Result/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6008` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / IsNamespaceSubset | `i=1001` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / NamespacePublicationDate | `i=1002` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / NamespaceUri | `i=1003` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / NamespaceVersion | `i=1004` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / StaticNodeIdTypes | `i=1005` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=1006` | value | read (default) |
| PADIM | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/PADIM/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=1007` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / IsNamespaceSubset | `i=13220` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / NamespacePublicationDate | `i=13221` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / NamespaceUri | `i=13222` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / NamespaceVersion | `i=13676` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / StaticNodeIdTypes | `i=13677` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=13678` | value | read (default) |
| Pumps | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/Pumps/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=13679` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / IsNamespaceSubset | `i=6004` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / NamespacePublicationDate | `i=6009` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / NamespaceUri | `i=6010` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / NamespaceVersion | `i=6011` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / StaticNodeIdTypes | `i=6012` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / StaticNumericNodeIdRange | `i=6013` | value | read (default) |
| TMC/v2 | Namespaces (`i=11715`) | <http://opcfoundation.org/UA/TMC/v2/> (NamespaceMetadata) / StaticStringNodeIdPattern | `i=6014` | value | read (default) |

## Server capabilities

Server specific limits/settings added by a companion specification.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| DI | ServerCapabilities (`i=2268`) | MaxInactiveLockTime | `i=6387` | - | read (default) |

## Role configuration

Well-known roles: identity/application/endpoint mappings are configured per server.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | RoleSet (`i=15606`) | Anonymous / Applications | `i=16193` | - | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / ApplicationsExclude | `i=15412` | - | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / Endpoints | `i=16194` | - | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / EndpointsExclude | `i=15413` | - | read (default) |
| core | RoleSet (`i=15606`) | Anonymous / Identities | `i=16192` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / Applications | `i=16204` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / ApplicationsExclude | `i=15414` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / CustomConfiguration | `i=24141` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / Endpoints | `i=16205` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / EndpointsExclude | `i=15415` | - | read (default) |
| core | RoleSet (`i=15606`) | AuthenticatedUser / Identities | `i=16203` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / Applications | `i=16270` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / ApplicationsExclude | `i=15428` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / CustomConfiguration | `i=24146` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / Endpoints | `i=16271` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / EndpointsExclude | `i=15429` | - | read (default) |
| core | RoleSet (`i=15606`) | ConfigureAdmin / Identities | `i=16269` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / Applications | `i=16237` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / ApplicationsExclude | `i=15424` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / CustomConfiguration | `i=24144` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / Endpoints | `i=16238` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / EndpointsExclude | `i=15425` | - | read (default) |
| core | RoleSet (`i=15606`) | Engineer / Identities | `i=16236` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / Applications | `i=16215` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / ApplicationsExclude | `i=15416` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / CustomConfiguration | `i=24142` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / Endpoints | `i=16216` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / EndpointsExclude | `i=15417` | - | read (default) |
| core | RoleSet (`i=15606`) | Observer / Identities | `i=16214` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / Applications | `i=16226` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / ApplicationsExclude | `i=15418` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / CustomConfiguration | `i=24143` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / Endpoints | `i=16227` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / EndpointsExclude | `i=15423` | - | read (default) |
| core | RoleSet (`i=15606`) | Operator / Identities | `i=16225` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / Applications | `i=16259` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / ApplicationsExclude | `i=15430` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / CustomConfiguration | `i=24147` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / Endpoints | `i=16260` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / EndpointsExclude | `i=15527` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityAdmin / Identities | `i=16258` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / Applications | `i=25606` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / ApplicationsExclude | `i=25605` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / CustomConfiguration | `i=25609` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / Endpoints | `i=25608` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / EndpointsExclude | `i=25607` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAccess / Identities | `i=25604` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / Applications | `i=25568` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / ApplicationsExclude | `i=25567` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / CustomConfiguration | `i=25571` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / Endpoints | `i=25570` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / EndpointsExclude | `i=25569` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerAdmin / Identities | `i=25566` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / Applications | `i=25587` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / ApplicationsExclude | `i=25586` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / CustomConfiguration | `i=25590` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / Endpoints | `i=25589` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / EndpointsExclude | `i=25588` | - | read (default) |
| core | RoleSet (`i=15606`) | SecurityKeyServerPush / Identities | `i=25585` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / Applications | `i=16248` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / ApplicationsExclude | `i=15426` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / CustomConfiguration | `i=24145` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / Endpoints | `i=16249` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / EndpointsExclude | `i=15427` | - | read (default) |
| core | RoleSet (`i=15606`) | Supervisor / Identities | `i=16247` | - | read (default) |

## Certificates / TrustList

Certificate groups and TrustList file: server security configuration and state.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Server (`i=2253`) | ServerConfiguration / ApplicationType | `i=25707` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / ApplicationUri | `i=25706` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / CertificateTypes | `i=14161` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / LastUpdateTime | `i=12662` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / OpenCount | `i=12646` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Size | `i=12643` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / UserWritable | `i=14158` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultApplicationGroup / TrustList / Writable | `i=14157` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / CertificateTypes | `i=14121` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / LastUpdateTime | `i=14110` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / OpenCount | `i=14093` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Size | `i=14090` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / UserWritable | `i=14092` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultHttpsGroup / TrustList / Writable | `i=14091` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / CertificateTypes | `i=14155` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / LastUpdateTime | `i=14144` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / OpenCount | `i=14127` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Size | `i=14124` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / UserWritable | `i=14126` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / CertificateGroups / DefaultUserTokenGroup / TrustList / Writable | `i=14125` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / HasSecureElement | `i=23597` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / MaxTrustListSize | `i=12640` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / MulticastDnsEnabled | `i=12641` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / ProductUri | `i=25725` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / ServerCapabilities | `i=12710` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / SupportedPrivateKeyFormats | `i=12639` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / PasswordLength | `i=24302` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / PasswordOptions | `i=24303` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / PasswordRestrictions | `i=24291` | - | read (default) |
| core | Server (`i=2253`) | ServerConfiguration / UserManagement / Users | `i=24301` | - | read (default) |

## PubSub

PublishSubscribe configuration, capabilities, status and diagnostics: server configuration and state.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Server (`i=2253`) | PublishSubscribe / ConfigurationProperties | `i=32404` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / ConfigurationVersion | `i=25481` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / DefaultDatagramPublisherId | `i=25480` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / DefaultSecurityKeyServices | `i=32403` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateDisabledByMethod | `i=17451` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateDisabledByMethod / Active | `i=17452` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateDisabledByMethod / Classification | `i=17453` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateDisabledByMethod / DiagnosticsLevel | `i=17454` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateError | `i=17424` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateError / Active | `i=17425` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateError / Classification | `i=17426` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateError / DiagnosticsLevel | `i=17429` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByMethod | `i=17431` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByMethod / Active | `i=17432` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByMethod / Classification | `i=17433` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByMethod / DiagnosticsLevel | `i=17434` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByParent | `i=17436` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByParent / Active | `i=17437` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByParent / Classification | `i=17438` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalByParent / DiagnosticsLevel | `i=17439` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalFromError | `i=17441` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalFromError / Active | `i=17442` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalFromError / Classification | `i=17443` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StateOperationalFromError / DiagnosticsLevel | `i=17444` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StatePausedByParent | `i=17446` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StatePausedByParent / Active | `i=17447` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StatePausedByParent / Classification | `i=17448` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / Counters / StatePausedByParent / DiagnosticsLevel | `i=17449` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / DiagnosticsLevel | `i=17410` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / ConfiguredDataSetReaders | `i=17460` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / ConfiguredDataSetReaders / DiagnosticsLevel | `i=17461` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / ConfiguredDataSetWriters | `i=17458` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / ConfiguredDataSetWriters / DiagnosticsLevel | `i=17459` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / OperationalDataSetReaders | `i=17464` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / OperationalDataSetReaders / DiagnosticsLevel | `i=17466` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / OperationalDataSetWriters | `i=17462` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / LiveValues / OperationalDataSetWriters / DiagnosticsLevel | `i=17463` | value | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / SubError | `i=17422` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalError | `i=17416` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalError / Active | `i=17417` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalError / Classification | `i=17418` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalError / DiagnosticsLevel | `i=17419` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalInformation | `i=17411` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalInformation / Active | `i=17412` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalInformation / Classification | `i=17413` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Diagnostics / TotalInformation / DiagnosticsLevel | `i=17414` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxDataSetReaders | `i=23683` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxDataSetWriters | `i=23682` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxDataSetWritersPerGroup | `i=32398` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxFieldsPerDataSet | `i=23684` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxNetworkMessageSizeBroker | `i=32400` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxNetworkMessageSizeDatagram | `i=32399` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxPubSubConnections | `i=23679` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxPublishedDataSets | `i=32841` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxPushTargets | `i=32840` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxReaderGroups | `i=23681` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxSecurityGroups | `i=32839` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxStandaloneSubscribedDataSets | `i=32842` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / MaxWriterGroups | `i=23680` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / SupportSecurityKeyPull | `i=32401` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / SupportSecurityKeyPush | `i=32402` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubCapablities / SupportSecurityKeyServer | `i=32843` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / OpenCount | `i=25455` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Size | `i=25452` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / UserWritable | `i=25454` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / PubSubConfiguration / Writable | `i=25453` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / Status / State | `i=17406` | - | read (default) |
| core | Server (`i=2253`) | PublishSubscribe / SupportedTransportProfiles | `i=17481` | - | read (default) |

## Historian defaults

Default historical data/event and aggregate configuration: server configuration.

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Server (`i=2253`) | DefaultHAConfiguration / AggregateConfiguration / PercentDataBad | `i=32640` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / AggregateConfiguration / PercentDataGood | `i=32641` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / AggregateConfiguration / TreatUncertainAsBad | `i=32639` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / AggregateConfiguration / UseSlopedExtrapolation | `i=32642` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / Definition | `i=32645` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / ExceptionDeviation | `i=32648` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / ExceptionDeviationFormat | `i=32649` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / MaxCountStoredValues | `i=32753` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / MaxTimeInterval | `i=32646` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / MaxTimeStoredValues | `i=32752` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / MinTimeInterval | `i=32647` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / ServerTimestampSupported | `i=32682` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / StartOfArchive | `i=32650` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / StartOfOnlineArchive | `i=32656` | - | read (default) |
| core | Server (`i=2253`) | DefaultHAConfiguration / Stepped | `i=32644` | - | read (default) |
| core | Server (`i=2253`) | DefaultHEConfiguration / StartOfArchive | `i=32756` | - | read (default) |
| core | Server (`i=2253`) | DefaultHEConfiguration / StartOfOnlineArchive | `i=32757` | - | read (default) |

## Other

| Namespace | Dynamic ancestor | Path below it | NodeId | Value | Access |
|---|---|---|---|---|---|
| core | Server (`i=2253`) | Resources / ProvisionableDevice / IsSingleton | `i=29879` | - | read (default) |
