"""Prompt templates for transcript summarization.

Provides system prompts for different summary styles (executive, action-items, detailed)
in multiple languages (English, Spanish), plus auto-detection of the best style based
on transcript content.
"""

# Prompt templates organized by style, then language
PROMPT_TEMPLATES = {
    "executive": {
        "en": """You are an expert at creating executive summaries from meeting transcripts.

Create a concise executive summary with these sections:

## Key Takeaways
- 3-5 bullet points of the most important insights

## Decisions Made
- List major decisions or conclusions reached

## Topics Covered
- Brief list of main discussion topics

Keep it under 300 words. Use clear, professional language.""",

        "es": """Eres un experto en crear resúmenes ejecutivos de transcripciones de reuniones.

Crea un resumen ejecutivo conciso con estas secciones:

## Puntos Clave
- 3-5 puntos de las ideas más importantes

## Decisiones Tomadas
- Lista de decisiones principales o conclusiones alcanzadas

## Temas Tratados
- Lista breve de los temas principales de discusión

Mantenlo en menos de 300 palabras. Usa lenguaje claro y profesional."""
    },

    "action-items": {
        "en": """You are an expert at extracting action items from meeting transcripts.

Create a summary focused on action items:

## Action Items
For each action item, provide:
- **Task**: Clear description of what needs to be done
- **Owner**: Person responsible (if mentioned)
- **Due Date**: Deadline (if mentioned, or "TBD")
- **Priority**: High/Medium/Low (infer from context)

## Key Decisions
- Brief list of decisions that led to these actions

## Next Steps
- Summary of what happens next

Format action items as a table for clarity.""",

        "es": """Eres un experto en extraer elementos de acción de transcripciones de reuniones.

Crea un resumen enfocado en elementos de acción:

## Elementos de Acción
Para cada elemento de acción, proporciona:
- **Tarea**: Descripción clara de lo que debe hacerse
- **Responsable**: Persona responsable (si se menciona)
- **Fecha límite**: Plazo (si se menciona, o "Por definir")
- **Prioridad**: Alta/Media/Baja (inferir del contexto)

## Decisiones Clave
- Lista breve de decisiones que llevaron a estas acciones

## Próximos Pasos
- Resumen de qué sucede después

Formatea los elementos de acción como una tabla para mayor claridad."""
    },

    "detailed": {
        "en": """You are an expert at creating detailed summaries from transcripts.

Create a comprehensive summary with these sections:

## Overview
- 2-3 paragraph executive summary

## Key Points
- Detailed bullet points covering all major topics discussed
- Include supporting details, examples, or data mentioned

## Decisions and Conclusions
- List all decisions made with context
- Include rationale where discussed

## Action Items
- Tasks assigned with owners and deadlines (if mentioned)

## Open Questions
- Any unresolved issues or questions for follow-up

Be thorough but stay organized with clear headings.""",

        "es": """Eres un experto en crear resúmenes detallados de transcripciones.

Crea un resumen completo con estas secciones:

## Visión General
- Resumen ejecutivo de 2-3 párrafos

## Puntos Clave
- Puntos detallados cubriendo todos los temas principales discutidos
- Incluye detalles de apoyo, ejemplos o datos mencionados

## Decisiones y Conclusiones
- Lista de todas las decisiones tomadas con contexto
- Incluye la justificación cuando se discutió

## Elementos de Acción
- Tareas asignadas con responsables y plazos (si se mencionan)

## Preguntas Abiertas
- Cualquier problema o pregunta sin resolver para seguimiento

Sé exhaustivo pero mantén la organización con encabezados claros."""
    }
}


def get_system_prompt(style: str, language: str = "en") -> str:
    """Get system prompt template for given style and language.

    Args:
        style: Summary style (executive, action-items, detailed)
        language: Language code (en, es)

    Returns:
        System prompt string. Defaults to executive/en if inputs invalid.
    """
    # Normalize inputs
    style = style.lower().replace("_", "-")
    language = language.lower()

    # Default to English if language not supported
    if language not in ["en", "es"]:
        language = "en"

    # Default to executive if style not found
    if style not in PROMPT_TEMPLATES:
        style = "executive"

    return PROMPT_TEMPLATES[style][language]


def detect_summary_style(transcript_text: str) -> str:
    """Auto-detect best summary style based on transcript content.

    Args:
        transcript_text: Full transcript text

    Returns:
        Summary style: "action-items", "detailed", or "executive"

    Heuristics:
        - Action items: Presence of task/action keywords
        - Executive: Default for most content (meetings, presentations)
        - Detailed: Long technical content (>10K words) with complex topics
    """
    text_lower = transcript_text.lower()
    word_count = len(transcript_text.split())

    # Check for action item indicators (English and Spanish)
    action_keywords = [
        "task", "action item", "assign", "due", "deadline",
        "follow up", "next step", "todo", "to do",
        "tarea", "acción", "asignar", "fecha límite",
        "seguimiento", "próximo paso"
    ]
    action_matches = sum(text_lower.count(keyword) for keyword in action_keywords)

    # High density of action keywords -> action-items style
    if action_matches >= 5 or (action_matches >= 3 and word_count < 3000):
        return "action-items"

    # Very long technical content -> detailed style
    if word_count > 10000:
        technical_keywords = [
            "implementation", "architecture", "design",
            "specification", "algorithm", "protocol",
            "implementación", "arquitectura", "diseño",
            "especificación", "algoritmo", "protocolo"
        ]
        tech_matches = sum(text_lower.count(keyword) for keyword in technical_keywords)
        if tech_matches >= 10:
            return "detailed"

    # Default: executive summary (most common use case)
    return "executive"
