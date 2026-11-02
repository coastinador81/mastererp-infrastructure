# Reparación limitada de base DEV (us-west-1)

Onboarding mantiene su stack propietario mastererp-dev-onboarding y Admin API qx8nmypdhi. La raíz funcional resources.yml parte de get-template Original real; no es una reorganización ni un bootstrap. Conserva sus recursos históricos sin recrearlos. Solo sesiones/progreso reciben paquete, red de aplicación existente y acceso al secreto mastererp_app exacto, más permisos ENI estándar de Lambda en VPC. No se cambia Cognito, RDS, red física, CORS ni definiciones del API.

Causa 500 comprobada en CloudWatch: KeyError al usar el campo reservado message en logging.extra. Además había secreto/pool/client vacíos, sin VPC y autenticación antigua por email/grupos. Backend ahora valida firma y contrato access antes de RDS, usa issuer/sub y contexto transaccional con rol de aplicación/TLS verify-full. Los logs contienen solo auditoría fija de actor/tenant/operación/resultado/correlación.

## Empaquetar y desplegar

En Platform, obtener el ZIP de dependencias Linux del artefacto histórico conservado:

```powershell
aws s3 cp s3://aws-sam-cli-managed-default-samclisourcebucket-sxnqlc5ufsez/mastererp-dev-onboarding/f011d5204089951f5d514239e4ead9f2 "$env:TEMP/onboarding-baseline.zip" --profile mastererp-admin --region us-west-1
py scripts/package_onboarding.py "$env:TEMP/onboarding-reviewed.zip" --dependency-zip "$env:TEMP/onboarding-baseline.zip"
```

El SHA base64 exigido es x+gtWZli7bgxQQFIm/atMT2OCw4DPwhhOqNDvZpjiO4=. Solo se copian dependencias revisadas y código actual de las tres funciones existentes; no mocks, .env, credenciales ni handlers retirados. Claves públicas Cognito se descargan al construir, no secretos. Ante rotación kid desconocido se rechaza; repetir empaquetado y despliegue. Dependencias nuevas requieren revisión del baseline, nunca desactivar la comprobación.

En Infrastructure:

```powershell
py scripts/repair_onboarding.py --artifact "$env:TEMP/onboarding-reviewed.zip" --output "$env:TEMP/onboarding-repair"
# Revisar change-set.json y definición API procesada equivalente antes de:
py scripts/repair_onboarding.py --artifact "$env:TEMP/onboarding-reviewed.zip" --output "$env:TEMP/onboarding-repair" --execute
```

No Add/Delete/Replace; el guard frena si otro desarrollador cambió recursos fuera del lote. SAM predice Modify dinámico del Body por las dos referencias ARN; solo se acepta si las definiciones procesadas son idénticas y las funciones no se reemplazan. Se comprueban IDs, rutas, integraciones y CORS después. El artefacto se sube al bucket SAM existente; no se crea bucket ni otro stack.

## Recuperación y alcance

Conservar original.json, change-set.json y ZIP previo fuera de Git. Ante fallo, no reintentar automáticamente ni ampliar permisos. Inspeccionar estado/events de CloudFormation y restaurar el artefacto/configuración previa por change set revisado, sin recrear funciones ni tocar APIs. La recuperación de código no revierte SQL 007, confirmado independientemente y respaldado en Database.

Las seis rutas heredadas hacia funciones ausentes permanecen pendientes. La aprobación de registro propio corresponde al usuario interno activo autenticado, no a asociación por correo o acceso universal; el flag queda false hasta reparar y validar ese recorrido. Las ocho funciones de Administración siguen siendo health técnicos. No se implementa Finanzas.

Pruebas SQL, unitarias Linux y HTTP se distinguen en sus informes; no afirmar cierre mientras queden casos funcionales sin demostrar.

## Uonify: solo artefacto del stack vigente

El helper compartido de 007 se integra en la consulta de estado, con módulo uonify.core activo y permiso vigente. Empaquetar desde Platform con el package.py publicado y las dependencias fijadas requirements-package.txt; el ZIP incluye foundation_access.py. No se toca frontend ni hosting.

```powershell
# Dependencias puras en carpeta temporal, mediante el mecanismo existente de empaquetado.
py -m pip install --no-compile --target "$env:TEMP/uonify-deps" -r backend/modules/0-uonify/lambdas/uonify-google-connection-handler/requirements-package.txt
py backend/modules/0-uonify/lambdas/uonify-google-connection-handler/package.py "$env:TEMP/uonify-reviewed.zip" --dependencies "$env:TEMP/uonify-deps"
# Infrastructure: prepara primero el change set y después ejecútalo.
py scripts/update_uonify_artifact.py --artifact "$env:TEMP/uonify-reviewed.zip" --output "$env:TEMP/uonify-plan"
py scripts/update_uonify_artifact.py --artifact "$env:TEMP/uonify-reviewed.zip" --output "$env:TEMP/uonify-plan" --execute
```

UsePreviousTemplate y solo ArtifactKey en mastererp-dev-uonify-google-connection. No se despliegan las plantillas locales ajenas de hosting/identidad. No cambia configuración, rol, VPC, rutas, scopes o CORS; se comprueban antes/después. Dependencias ya presentes se pueden reutilizar tras comprobar sus versiones, sin instalar herramientas.
