# Recursos Clientes/Proveedores DEV

API administrativo qx8nmypdhi propiedad vigente de mastererp-dev-onboarding. Se añade AdminCognitoJwtAuthorizer para el pool/cliente compartidos existentes y se amplía CORS de forma aditiva con X-MasterERP-Tenant-Id y app-dev.uonify.com; no se cambia autenticación de rutas existentes. modules/api-gateways.yml sigue en transición y NO se despliega como reemplazo. Esta excepción de ubicación física está explícita: el autorizador pertenece a APIs compartidas y se declara temporalmente en el propietario actual, no en Clientes ni Proveedores.

Finanzas mastererp-dev-finance conserva el hijo mastererp-dev-administration. Cada capacidad declara función, rol, log, integración, rutas y permisos en el resources.yml raíz de su carpeta funcional. El ensamblador produce 64 recursos (48 anteriores + 8 rutas y 8 permisos). Solo dos funciones/roles se actualizan; las integraciones/rutas tuvieron la recuperación descrita al final. Las otras seis Lambdas siguen siendo diagnósticos. No hay YAML ni stack por Lambda.

Parámetros explícitos del padre al hijo: referencia de autorizador, issuer/cliente, secreto de aplicación, host RDS, subnets privadas y SG existentes, además de artefactos versionados por hash. Roles permiten solo GetSecretValue del secreto exacto, logs propios y acciones ENI requeridas por Lambda en VPC (Resource * para APIs EC2 que lo requieren). Se reutiliza cifrado AWS administrado; no se crean claves, secretos, NAT, endpoints ni recursos de red. Python 3.12 arm64, 256 MB, timeout 15s e integración 15s.

Preparar artefactos con Platform/scripts/package_parties.py. Ejecutar desde Infrastructure:

```powershell
py scripts/deploy_parties.py --phase prepare-finance --output <mismo-directorio> --artifacts <ZIPs-Platform>
py scripts/deploy_parties.py --phase execute-finance --output <mismo-directorio>
```

Configuración de API: usar deploy_admin_api.py según ADMIN_API_DEPLOYMENT.md, solo cuando sea necesario. Preparación y ejecución de Finanzas separadas, revisión de change sets padre e hijo; se rechazan eliminaciones/reemplazos. Plantillas y ZIP anteriores se conservan en el bucket privado existente y en el plan local. No se recrean funciones retiradas ni se actualiza directamente el hijo. Para recuperar, preparar un change set inverso revisado con las referencias anteriores; no borrar stacks ni asumir que revertir código revierte datos.

Las rutas nuevas GET base/detalle, POST base y PATCH detalle usan JWT y scope existente mastererp-dev/identity.spaces.read. Permisos PostgreSQL siguen siendo la autoridad funcional. /health conserva su comportamiento técnico. La evidencia HTTP y SQL vive en Database/docs/parties-*.json; no se afirma capacidad funcional por un health 200.

## Incidencia de reimportación y recuperación

Al actualizar CORS mediante el propietario SAM, CloudFormation reimportó Body y eliminó las ocho integraciones/rutas health externas, además de cambiar IDs internos de rutas/integraciones de Onboarding. Se detectó por inventario antes de ejecutar el cambio funcional y se retiró el change set pendiente. Los API/endpoints, funciones, roles, logs y permisos existentes se conservaron. No hubo cambios en datos.

Se confirmó por AWS la ausencia de los 16 recursos físicos del hijo. Las plantillas propietarias declaran IntegrationRecovered y HealthRouteRecovered y se actualiza el mismo stack anidado. La recuperación retira del estado solo las declaraciones cuyos recursos físicos ya no existen y crea reemplazos con URLs/destinos equivalentes. Los IDs antiguos no son recuperables y no se afirma preservación de ellos. La revisión del plan permite esas retiradas exclusivamente tras comprobar otra vez su ausencia en AWS; no permite borrar recursos vivos. Se conservan los nombres/IDs de Lambdas, roles, logs y permisos.

Advertencia para DevOps: mientras Admin API permanezca definido por Body de SAM y existan rutas externas, NO actualizar ese Body/CORS sin inventario y plan de preservación. La separación definitiva de propiedad requiere otra entrega; no se hace una migración global aquí. Esta entrega incorpora una incidencia real y su recuperación, no solo los cambios inicialmente previstos.

Actualizaciones posteriores de código: ejecutar únicamente prepare-finance/execute-finance. Las fases prepare-api/execute-api ya no existen; no reimportar Body para actualizar artefactos. El plan de recuperación solo se utiliza para recursos que todavía aparecen en el estado anterior y cuya ausencia física se verificó.

## Resultado verificado DEV

Desplegado: 33 comprobaciones HTTP funcionales aprobadas, con persistencia, idempotencia, versiones, permisos, aislamiento y limpieza acotada. Evidencia principal en Database/docs/ADMINISTRATION_PARTIES_DEV.md y parties-http-validation.json. Se documentan aparte los tres 403 previos de Uonify y la incidencia de reimportación SAM recuperada con nuevos IDs de rutas/integraciones. Las ocho Lambdas conservaron sus IDs y las otras seis su código.

## Actualización del mecanismo de API

El riesgo de reimportación descrito arriba se resuelve en [el procedimiento nativo](ADMIN_API_DEPLOYMENT.md): las fases históricas prepare-api/execute-api se retiran. Para Clientes/Proveedores se conserva prepare-finance/execute-finance; la configuración compartida se actualiza con deploy_admin_api.py y rutas/integraciones son recursos individuales. No repetir el procedimiento antiguo de CORS/SAM.
