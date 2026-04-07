# OpenClaw — Contexto Maestro para Claude Code

**Versión:** v1.0
**Fecha:** 2026-03-12
**Estado:** Activo
**Idioma de trabajo:** Español
**Propósito:** Este documento es la fuente principal de verdad para el trabajo de Claude Code sobre OpenClaw. No es una nota informal. Es una especificación operativa de contexto, alcance, prioridades, reglas y límites.

---

# 1) One-liner del proyecto

**OpenClaw es una plataforma modular de captación, cualificación y activación de leads, diseñada para operar primero como motor interno y evolucionar hacia producto vendible multi-vertical con bajo mantenimiento, alta reutilización y control estricto del riesgo.**

---

# 2) Objetivo de negocio a 12 meses

## Meta principal
- Alcanzar **20 clientes activos** que adquieran producto o servicio basado en OpenClaw.
- Mantener **bajo mantenimiento** operativo.
- Evitar **gasto elevado** desproporcionado.
- Lograr **~200.000 € anuales de beneficio**.

## Principio económico
OpenClaw no existe para demostrar sofisticación técnica. Existe para:
- generar valor económico real,
- reducir errores caros,
- reutilizar trabajo entre verticales,
- y crear una base vendible a terceros.

---

# 3) Estrategia general del producto

## Tesis
Los negocios propios del fundador pueden usarse como **laboratorio de prueba** para detectar fallos, afinar procesos y validar diseño, pero OpenClaw debe construirse con intención de ser **vendible a terceros** relativamente pronto.

## Regla estratégica
Los negocios propios sirven como banco de pruebas, **no como cárcel de requisitos**. Las necesidades internas no deben forzar una solución tan específica que destruya la reutilización futura.

---

# 4) MVP actual vs visión futura

## 4.1 MVP comercial actual (en foco)
El MVP actual se centra en una **fábrica de leads usable**:
- captación / ingesta de leads,
- validación mínima,
- scoring,
- clasificación,
- enriquecimiento selectivo,
- Lead Pack,
- entrega / activación básica,
- trazabilidad de origen,
- avisos operativos,
- ingesta externa mínima por webhook/form.

## 4.2 Visión futura (fuera del foco inmediato)
Puede incluir más adelante:
- CRM más profundo,
- booking/citas,
- WhatsApp avanzado general,
- dashboards avanzados,
- automatizaciones cross-module complejas,
- verticales altamente personalizadas,
- módulos de trading/risk separados,
- producto más completo para terceros.

## Regla
La visión futura **no puede contaminar** el MVP comercial actual salvo cuando cree infraestructura reusable, evite retrabajo probable o reduzca riesgo relevante.

---

# 5) Verticales y orden de prioridad actual

## Orden provisional de prioridad
1. **Barcos**
2. **Reformas**
3. **Inmobiliaria**
4. **Viajes**
5. **Luminaria / electrónica náutica**

## Lectura estratégica
- **Barcos**: vertical plantilla por afinidad, ticket y valor estratégico.
- **Reformas**: potencial de validación comercial más rápida.
- **Inmobiliaria**: gran potencial de datos y reutilización.
- **Viajes**: útil, pero no debe desordenar el core.
- **Luminaria/electrónica náutica**: vertical especializada complementaria.

## Regla
El sistema debe adaptarse a nuevas verticales por **core común + configuración + ajustes por vertical** antes de pasar a pipelines casi independientes.

---

# 6) Prioridades reales del producto (corregidas para MVP)

Para el **MVP de leads**, el orden de prioridad operativo es:
1. **Calidad del lead**
2. **Ingresos rápidos / validación comercial real**
3. **Reutilización entre verticales**
4. **Robustez técnica suficiente**
5. **Escalabilidad futura**
6. **Reducción de horas humanas**

## Nota
La visión general del proyecto valora mucho escalabilidad y reutilización, pero en el MVP comercial no deben imponerse por delante de una máquina de leads que ya funcione, convierta y no genere caos.

---

# 7) Antiobjetivos

OpenClaw **no debe convertirse** en:
- una catedral técnica lenta de adaptar,
- un pseudo-CRM inflado antes de demostrar que el pipeline de leads funciona,
- una plataforma dependiente de demasiadas integraciones frágiles en el MVP,
- un chatbot bonito sin valor económico claro,
- una mezcla peligrosa entre core comercial y trading,
- una arquitectura tan abstracta que cueste adaptarla a negocio real,
- un sistema que automatice acciones sensibles solo porque técnicamente puede.

---

# 8) Principios no negociables

1. **No sobreingenierizar.**
2. **No duplicar lógica si puede evitarse limpiamente.**
3. **No tocar schema persistido sin necesidad clara.**
4. **No romper compatibilidad con flujos existentes sin justificación fuerte.**
5. **No perder trazabilidad del origen del lead.**
6. **No sacrificar calidad del lead por automatización vistosa.**
7. **No abrir nuevos frentes si el bloque actual puede cerrarse con pocos cambios quirúrgicos.**
8. **Toda deuda técnica diferida debe quedar anotada.**
9. **La validación determinista debe preferirse frente a IA/triada cuando baste.**
10. **El coste y la latencia importan; no se añade complejidad si no mejora negocio, riesgo o reutilización.**

---

# 9) Decisiones ya congeladas

## Triada y arquitectura general
- En **Market Data** no se usa triada; ahí solo validación determinista (schema, integridad, checksum, dedupe).
- La triada **solo** se usa en decisiones de alto impacto.
- En Automations MVP, la triada se activa en **modo B (scoring_only)** con triggers duros y solo sobre un subconjunto configurable de leads.
- Trading y módulos de alto riesgo deben permanecer **aislados** del core comercial.

## Módulo leads
- El módulo leads MVP se considera prácticamente cerrado salvo deudas explícitas y nueva ingesta externa mínima.
- Tras cerrar leads MVP, la siguiente prioridad es **ingesta externa mínima por webhook/form**.
- El sistema debe evitar reabrir el módulo leads salvo ajustes muy rentables, muy claros o ya anotados.

## Formato y modelo
- Clasificación visible principal: **hot / warm / cold**.
- Scoring: **score numérico + clasificación**.
- Modelo actual: **core común fuerte + ajustes por vertical**.
- Salida canónica: **JSON**.
- Salida humana operativa MVP: **HTML**.
- Lead Pack MVP: **corto y accionable**.
- Enriquecimiento MVP: **selectivo, no universal**.

## Duplicados
- Duplicado fuerte: **mismo email o mismo teléfono**.
- Duplicado probable: reglas blandas; no merge automático.

---

# 10) Deuda explícita ya aceptada

## Deuda conocida del módulo leads
- El campo `source` compuesto solo por whitespace hoy puede acabar persistido como `""`.
- Esta corrección se difirió para no reabrir validación/schema en ese bloque.

## Política de deuda aceptada
Toda deuda técnica diferida debe registrarse con:
- descripción,
- impacto,
- motivo de aplazamiento,
- condición de reapertura.

---

# 11) Definición de "hecho" (Definition of Done)

Un bloque se considera terminado solo si:
- funciona,
- tiene tests mínimos útiles,
- no rompe compatibilidad,
- deja deuda anotada si existe,
- deja documentación breve actualizada,
- y no incluye refactor oportunista fuera de alcance.

## Regla
No se refactoriza por gusto durante un bloque si esa refactorización no reduce riesgo claro, duplicación relevante o coste futuro probable.

---

# 12) Política de cambios de alcance

Si durante un bloque aparece una mejora no imprescindible:
- se documenta como **follow-up**, y
- no se implementa en el mismo bloque salvo que:
  - desbloquee el objetivo actual,
  - reduzca riesgo material,
  - evite retrabajo casi seguro,
  - o cree infraestructura reusable mínima claramente justificada.

---

# 13) Reglas maestras de trabajo para Claude Code

## Prioridad y foco
1. Cuando haya conflicto entre elegancia técnica y velocidad del MVP comercial, se prioriza la solución más simple que **no comprometa** calidad del lead, trazabilidad ni mantenibilidad básica.
2. Cuando haya conflicto entre añadir una feature nueva y cerrar bien una feature abierta, se prioriza **cerrar bien lo abierto**.
3. No se abre un nuevo frente si el bloque actual puede cerrarse con pocos cambios quirúrgicos.
4. Toda mejora no imprescindible detectada durante un bloque se documenta como follow-up y no se implementa en el mismo bloque salvo justificación fuerte.

## Calidad
5. No se acepta una mejora que aumente complejidad si no aporta al menos una de estas: más conversión, menos pérdida de leads válidos, menos errores operativos, más trazabilidad útil o menor coste real a medio plazo.
6. En MVP se prefiere **robustez operativa suficiente** antes que perfección arquitectónica.
7. Fallos especialmente inaceptables en leads:
   - perder leads válidos,
   - score absurdo,
   - salida automática incorrecta,
   - pérdida de trazabilidad del origen.
8. Si una decisión técnica mejora rendimiento pero complica demasiado comprensión, observabilidad o depuración, se rechaza en MVP salvo necesidad clara.

## Autonomía
9. Claude Code puede proponer alternativas, pero debe ejecutar por defecto la opción más pragmática y alineada con decisiones congeladas.
10. Claude Code no debe reinterpretar ni reabrir decisiones de negocio cerradas salvo contradicción fuerte, riesgo material o imposibilidad técnica real.
11. Claude Code no debe tocar schema persistido, scoring de negocio, reglas de descarte ni comportamiento crítico de automatización sin justificarlo explícitamente.
12. Claude Code no debe añadir abstracciones, capas o patrones "por si acaso" sin necesidad inmediata demostrable.

## Coste y latencia
13. En MVP, cualquier paso que añada coste por lead o latencia debe justificarse por mejora clara en calidad, conversión o reducción de riesgo.
14. El enriquecimiento, la triada o cualquier procesamiento adicional debe ser selectivo, no universal, salvo que sea muy barato y muy fiable.
15. No se optimiza para máximo detalle si ese detalle no se va a usar operativamente o comercialmente en las siguientes semanas.

## Arquitectura del producto
16. OpenClaw se diseña como plataforma modular reusable, pero el MVP actual debe priorizar una **fábrica de leads usable** antes que una plataforma generalista completa.
17. El core compartido debe ser lo bastante fuerte para reutilizarse entre verticales, pero no tan abstracto que dificulte adaptar barcos, reformas o inmobiliaria.
18. La personalización por vertical se implementa primero por configuración, pesos, campos opcionales y reglas simples, no por pipelines completamente separados salvo necesidad demostrada.
19. Trading y otros módulos de alto riesgo deben permanecer aislados del core comercial y no influir en el diseño del MVP de leads.

## Testing y cierre
20. Todo bloque se considera terminado solo si cumple la Definition of Done de este documento.
21. No se refactoriza por gusto durante un bloque si la refactorización no reduce riesgo claro, duplicación relevante o coste futuro probable.
22. Toda deuda técnica diferida debe quedar registrada con descripción, impacto, motivo y condición de reapertura.

## Contexto y memoria
23. El contexto maestro debe distinguir siempre entre:
   - decisiones congeladas,
   - supuestos provisionales,
   - preguntas abiertas,
   - deuda aceptada.
24. Si hay ambigüedad entre una conversación antigua y una decisión más reciente documentada, manda la decisión más reciente documentada.
25. Claude Code debe trabajar con este contexto maestro como fuente principal de verdad para producto y alcance, no solo con el prompt de la tarea aislada.

## Reglas comerciales del módulo leads
26. Todo lead válido genera salida mínima; solo leads de mayor valor generan enriquecimiento o salida ampliada.
27. Se prefiere conservar leads incompletos rescatables antes que descartarlos prematuramente, pero no se debe llenar el sistema de basura operativa.
28. La trazabilidad del origen no es un extra analítico: es parte del valor económico del sistema.
29. La clasificación y el scoring deben ayudar a vender y priorizar mejor, no solo a "puntuar bonito".
30. El output del sistema debe ser útil tanto para automatización como para lectura humana rápida.

## Antiobjetivos operativos
31. OpenClaw no debe convertirse en una catedral técnica lenta de adaptar.
32. OpenClaw no debe convertirse en un pseudo-CRM inflado antes de demostrar que el pipeline de leads ya funciona.
33. OpenClaw no debe depender de demasiadas integraciones frágiles en el MVP.
34. OpenClaw no debe automatizar acciones sensibles solo porque "se puede".
35. OpenClaw no debe perseguir sofisticación de IA donde bastan reglas claras y validación determinista.

## Regla 36 corregida (crítica)
36. Si una idea no mejora claramente el valor del bloque actual en el corto plazo, **no entra** salvo que:
   - cree infraestructura transversal reusable,
   - evite retrabajo probable,
   - reduzca riesgo importante,
   - habilite una vertical estratégica futura sin contaminar el MVP actual,
   - o su coste de implementación marginal ahora sea mucho menor que hacerlo después.

### Interpretación obligatoria de la Regla 36
La regla 36 **no significa** "si no monetiza en 30–60 días, fuera".
Sí permite trabajo fundacional si:
- crea infraestructura reusable,
- evita rehacer más adelante,
- reduce riesgo relevante,
- o habilita una vertical futura estratégica sin contaminar el MVP comercial.

### Regla de control para trabajo fundacional
Ningún trabajo "para futuro" entra en un bloque actual salvo que quede justificado por escrito como:
- infraestructura común reusable,
- prevención de retrabajo probable,
- o reducción de riesgo relevante.

Y aun así debe implementarse en la **forma mínima necesaria**.

## Docker, sandbox y autonomía táctica
37. Todo bloque nuevo debe validarse en entorno aislado; **Docker y sandbox forman parte de la estrategia de ejecución y aceptación técnica**.
38. Claude Code puede operar con **autonomía táctica** dentro de bloques definidos si valida en sandbox/tests y no viola decisiones congeladas, contratos ni límites de negocio.
39. Los módulos de alto riesgo como trading deben reutilizar la **infraestructura común** de OpenClaw, pero mantener lógica de negocio, validaciones y permisos **aislados** del core comercial.
40. El trabajo fundacional no orientado a ingresos inmediatos solo entra si aporta infraestructura reusable, evita retrabajo probable o reduce riesgo relevante, y debe hacerse en la forma mínima necesaria.

---

# 14) Contrato funcional del módulo leads (MVP)

## Objetivo del módulo
Recibir leads desde varias fuentes, validarlos mínimamente, deduplicarlos de forma básica, asignarles score y clasificación, enriquecer selectivamente los mejores, producir un pack útil y entregarlos de forma trazable a automatización o revisión humana.

## Flujo alto nivel
1. Ingesta
2. Validación mínima
3. Identificación de origen
4. Dedupe básico
5. Scoring
6. Clasificación
7. Enriquecimiento selectivo
8. Generación de salida (JSON + HTML)
9. Avisos según reglas
10. Entrega / revisión / siguiente acción

---

# 15) Lead válido, basura operativa y contexto suficiente

## 15.1 Definición mínima de lead válido
Un lead válido debe tener:
- al menos **un contacto útil** (`phone` o `email`),
- y **algo de contexto/intención**.

## 15.2 Definición de contexto suficiente
Un lead tiene contexto suficiente si incluye al menos una de estas:
- servicio solicitado,
- mensaje libre con intención comprensible,
- vertical clara,
- origen/campaña con intención fuerte,
- necesidad concreta,
- zona/ubicación relevante para el servicio.

## 15.3 Basura operativa
Se considera basura operativa un registro que:
- no tiene teléfono ni email útiles,
- y no tiene intención accionable,
- y no puede enriquecerse razonablemente,
- o es spam / manifiestamente irrelevante.

---

# 16) Campos universales del lead

## Campos canónicos mínimos
- `id`
- `source`
- `channel`
- `timestamp`
- `campaign` (opcional)
- `landing` (opcional)
- `name` (opcional)
- `phone` (opcional)
- `email` (opcional)
- `context`
- `vertical`
- `status`
- `score`
- `classification`
- `priority`
- `requires_enrichment`
- `premium_source`
- `fast_action`
- `next_action`

## Nota
No añadir más como core universal salvo justificación fuerte.

---

# 17) Estados del lead

Estados propuestos para MVP:
- `new`
- `validated`
- `needs_enrichment`
- `qualified`
- `duplicate_review`
- `delivered`
- `discarded`
- `error`

No expandir esta taxonomía sin necesidad clara.

---

# 18) Scoring y clasificación

## Formato
- Score numérico
- Clasificación visible: `hot / warm / cold`

## Umbrales iniciales
- `hot`: 75–100
- `warm`: 45–74
- `cold`: 0–44

## Principio
Estos umbrales son iniciales y ajustables con datos, pero sirven para arrancar sin ambigüedad.

## Prioridad base del scoring (corregida)
1. **Intención**
2. **Encaje con servicio**
3. **Calidad del contacto**
4. **Facilidad de cierre**
5. **Urgencia**
6. **Capacidad económica**

## Regla
La clasificación y el scoring existen para vender mejor, priorizar mejor y reducir errores, no para producir métricas bonitas.

---

# 19) Duplicados

## Duplicado fuerte
- mismo email,
- o mismo teléfono.

## Duplicado probable
- mismo nombre + misma empresa,
- o mismo nombre + contexto muy similar.

## Comportamiento MVP
- Duplicado fuerte → no crear lead nuevo limpio sin más; enlazar, actualizar o tratar como duplicado fuerte.
- Duplicado probable → marcar `duplicate_review`; no hacer merge automático.

---

# 20) Enriquecimiento MVP

## Qué enriquecer primero
- validación de teléfono/email,
- ubicación,
- empresa,
- web/dominio,
- tipo de necesidad / sector.

## Cuándo enriquecer
- leads `hot`,
- `warm` alto,
- `premium_source = true`,
- o revisión manual / regla específica lo fuerce.

## Regla
El enriquecimiento es selectivo. No enriquecer basura ni enriquecer universalmente por defecto.

---

# 21) Fuente premium y acción rápida

## Fuente premium
Una `premium_source` es una fuente que, para un vertical concreto, muestra una o más de estas señales:
- mayor intención,
- mejor calidad de contacto,
- mejor tasa de conversión histórica o esperada,
- mejor margen esperado,
- mejor completitud de datos.

### Implementación
La definición final debe hacerse por **configuración por vertical**, no hardcodeada por toda la lógica.

## Acción rápida
Un lead requiere `fast_action` si cumple una o más de estas:
- urgencia explícita,
- canal de respuesta inmediata,
- ventana de conversión corta,
- alto riesgo de perderse si no se responde pronto,
- señal fuerte de intención inmediata.

---

# 22) Salidas del módulo leads

## Salida mínima para todo lead válido
- score,
- clasificación,
- flags relevantes,
- siguiente acción,
- origen trazable,
- salida canónica JSON.

## Salida humana MVP
HTML con al menos:
- id del lead,
- vertical,
- fecha/hora,
- contacto disponible,
- origen,
- score,
- clasificación,
- prioridad comercial,
- resumen breve,
- siguiente acción,
- flags importantes:
  - `requires_enrichment`,
  - `duplicate_review`,
  - `premium_source`,
  - `fast_action`.

---

# 23) Lead Pack MVP

## Objetivo
Pack corto, accionable y útil tanto para automatización como para lectura humana rápida.

## Contenido mínimo
- contacto,
- origen,
- score,
- clasificación,
- prioridad comercial,
- resumen breve,
- siguiente acción,
- flag de enriquecimiento,
- datos enriquecidos si existen.

## Regla
No inflar el Lead Pack con relleno. Debe ayudar a actuar, no impresionar.

---

# 24) Avisos y entrega

## Triggers MVP de aviso
OpenClaw genera aviso cuando ocurre cualquiera de estos:
- lead `hot`,
- `fast_action = true`,
- `premium_source = true`,
- error de procesamiento,
- opcionalmente `warm` alto en verticales concretos.

## Regla de centralización
Los avisos los centraliza OpenClaw. Los agentes o módulos no notifican por su cuenta como sistema desordenado.

## Canal inicial recomendado
- Telegram o email interno como operativa inicial.
- **No WhatsApp** como canal interno principal en fase 1.
- WhatsApp sí puede existir como **fuente de entrada** y como salida cliente-facing si se configura expresamente.

## Orden de entrega MVP
1. automatización interna / OpenClaw,
2. revisión humana,
3. cliente final como salida posterior o configurable.

---

# 25) Alcance actual del siguiente bloque técnico

## Bloque activo tras cerrar leads MVP
Añadir una **ingesta externa mínima y usable** para leads, manteniendo enfoque MVP.

## Objetivo
Crear una entrada simple tipo webhook para recibir leads desde fuera sin romper el flujo actual.

## Alcance
- añadir un endpoint nuevo y mínimo para ingestión externa de leads,
- reutilizar al máximo la lógica actual de creación de leads,
- no duplicar lógica si se puede evitar limpiamente,
- mantener compatibilidad con `POST /leads` existente,
- definir forma simple de identificar origen externo si hace falta,
- añadir tests mínimos útiles,
- no tocar schema persistido,
- no tocar scoring.

## Fuera de alcance en este bloque
- rediseño general del módulo,
- scoring avanzado,
- triada nueva,
- refactor amplio no justificado,
- reabrir deudas no críticas del bloque anterior.

---

# 26) Uso de Docker y sandbox

## Regla operativa
Claude Code debe asumir que Docker y sandbox son herramientas de validación y aislamiento, no extras opcionales.

## Principios
- todo bloque nuevo debe poder probarse en entorno aislado cuando aplique,
- el resultado debe ser reproducible,
- el sandbox sirve para validar integración mínima y evitar aceptar bloques rotos,
- pasar sandbox no autoriza por sí solo cambios de negocio no aprobados.

---

# 27) Límites de autonomía de Claude Code

## Claude Code puede hacer solo
- implementar bloques definidos,
- proponer alternativas,
- escribir tests,
- validar en sandbox,
- refactorizar dentro del alcance,
- documentar deuda y decisiones,
- preparar salidas para revisión o entrega.

## Claude Code no puede hacer solo
- redefinir negocio,
- cambiar scoring de negocio sin aprobación,
- tocar schema persistido sin justificación clara,
- descartar leads valiosos agresivamente,
- responder por WhatsApp en clientes sensibles sin permiso,
- mezclar trading/risk con el core comercial,
- abrir frentes grandes no aprobados.

---

# 28) Supuestos provisionales (no congelados del todo)

Estos puntos siguen siendo provisionales y pueden afinarse con datos:
- definición exacta por vertical de `premium_source`,
- definición exacta por vertical de `fast_action`,
- pesos finales del scoring por vertical,
- umbrales definitivos hot/warm/cold,
- catálogo final de `next_action` si se amplía,
- nivel exacto de integración con cliente final,
- canales finales de notificación más allá de la fase inicial.

---

# 29) Preguntas aún abiertas que NO debe inventar Claude Code

Claude Code no debe inventar por su cuenta:
- definición comercial fina de lead bueno por vertical,
- reglas finales de scoring de negocio,
- qué automatizaciones sensibles se permiten exactamente,
- cuándo responder automáticamente por WhatsApp en producción,
- qué umbral activa enriquecimiento caro,
- qué vertical requiere excepciones profundas,
- qué parte del sistema se vende como producto estándar vs premium.

---

# 30) Instrucción final para Claude Code

Trabaja como si OpenClaw fuera un negocio real, no un ejercicio de arquitectura.
Prioriza claridad, reutilización sensata, bajo riesgo, compatibilidad, trazabilidad y avance real del MVP comercial.
No reabras decisiones congeladas sin motivo fuerte.
No sacrifiques el foco por ideas vistosas.
Y cuando haya duda, elige la solución **más simple, reusable y defendible** que respete este documento.
