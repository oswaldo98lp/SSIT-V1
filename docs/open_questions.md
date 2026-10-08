# Preguntas Abiertas y Valores por Defecto

Este documento registra ambigüedades, expresiones truncadas en la documentación de AppSheet (`docs/legacy/`) y temas pendientes de confirmación con el negocio.

| ID | Tema | Descripción / Página PDF | Valor por Defecto Asumido | Estado |
|---|---|---|---|---|
| Q-001 | Validación de existencias | Regla de stock estricto en surtido | Parametrizable vía `STOCK_VALIDATION` (default `False` en dev, `True` en prod) | RESUELTO |
| Q-002 | Autenticación | Credenciales corporativas Google SSO | Login local por email + Allauth preparado para OAuth2/Google SSO | RESUELTO |
| Q-003 | Roles heredados | Eventual, Encargado de soporte, Gerente titular | Creados desactivados y sin menú en `seed_roles` | RESUELTO |
| Q-004 | Catálogo de Zonas y Regiones | Definición inicial de 6 zonas y sus regiones | 6 zonas y 48 regiones pobladas idempotentemente en `seed_org` | RESUELTO |
| Q-005 | Ubicación de casos | Casos con location TALLER vs CENTRO | Región con `is_workshop` y caso con `location` (CENTRO o TALLER) | RESUELTO |
| Q-006 | Surtidos por vale | Surtidos parciales vs únicos | Surtido por línea con trazabilidad por número de serie individual | RESUELTO |
| Q-007 | Folio de reporte duplicado | Duplicidad en folio de reporte al crear vale | Advertencia no bloqueante con indexación en base de datos | RESUELTO |
| Q-008 | Formato de plantillas PDF | Plantillas oficiales de Vale y Regreso con QR | Diseños limpios profesionales con WeasyPrint en español de México | RESUELTO |
| Q-009 | Exportaciones XLSX | Compatibilidad con formatos Excel corporativos | Generación in-memory vía `openpyxl` con estilos y encabezados oscuros | RESUELTO |
| Q-010 | Conciliación de Inventario | Auditoría física vs movimientos teóricos de Kárdex | Motor de conciliación con clasificación de sobrantes, faltantes y tasa de concordancia | RESUELTO |

