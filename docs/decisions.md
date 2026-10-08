# Registro de Decisiones de Arquitectura y Diseño (ADR)

| ID | Fecha | Decisión | Justificación | Impacto |
|---|---|---|---|---|
| ADR-001 | 2026-10-07 | Estructura modular de 10 aplicaciones Django (`core`, `accounts`, `org`, `catalog`, `inventory`, `vouchers`, `cases`, `documents`, `reports`, `transitions`) | Separación clara de responsabilidades con capas (`models`, `selectors`, `services`, `forms`, `views`, `tables`, `filters`, `templates`, `tests`) | Alta mantenibilidad y aislamiento de capas |
| ADR-002 | 2026-10-07 | Motor de transiciones declarativo centralizado (`transitions/registry.py`) con control transaccional estricto (`select_for_update`) | Previene condiciones de carrera en surtido y cancelaciones; garantiza auditoría completa en `core_event` | Consistencia total en el ciclo de vida de inventario y casos |
| ADR-003 | 2026-10-07 | Interfaz UI Mobile-First con Django Templates + HTMX + Bootstrap 5 + django-tables2 | Soporte responsivo para ingenieros en campo (móvil) y personal de almacén/oficina (escritorio) sin complejidad excesiva de SPAs pesadas | Cargas rápidas, experiencia interactiva con modales dinámicos |
