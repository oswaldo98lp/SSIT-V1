# Reglas Permanentes - Admón Almacén SSIT 2.0

1. **Idioma**: Responde siempre en español. Código e identificadores en inglés. Textos UI en español de México.
2. **Fuente de verdad**: `docs/legacy/` es la fuente de verdad. No inventar reglas. Registrar dudas en `docs/open_questions.md`.
3. **Lógica de negocio**: Cada acción de negocio es una transición declarada (`transitions/registry.py`). Nada de lógica en vistas o plantillas; todo va en `services.py`.
4. **Alcance**: Todo queryset de negocio pasa por selectores con alcance (`user.allowed_regions()`). Prohibido consultar modelos de negocio sin alcance en vistas.
5. **Sin datos reales**: Prohibido escribir correos, regiones o nombres de personas en código. Usar datos sintéticos.
6. **Pruebas**: Pruebas junto con el código. Ninguna fase termina con pruebas en rojo. Cobertura en servicios >= 85%.
7. **Trazabilidad**: Reflejar cobertura en `docs/traceability.csv`.
8. **Control de fases**: Detenerse al terminar cada fase y esperar aprobación.
