# Solicitudes de compra

Responsabilidad general: Organizar las solicitudes de adquisición de bienes y servicios.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

`resources.yml` vacío: reserva documental excluida del despliegue. Los recursos compartidos se declararán una sola vez en el padre común correspondiente.

## Entrega básica de compras

Preparación de listado, detalle, creación y edición de borradores conectados a documentos existentes. Secuencia solicitud → orden → factura, sin aprobación ni efectos financieros automáticos. Lambda Compras existente; recursos exclusivos en el YAML raíz propietario. Ver [contrato y validación](../../../../../docs/PURCHASE_DRAFTS_DEV.md).
