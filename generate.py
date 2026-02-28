def generate_summary_with_ai(text, title):

    if not client:
        print("⚠ No hay cliente OpenAI. Usando fallback.")
        return fallback_summary(text)

    text = text[:3000]
    question_mode = is_question_title(title)

    if question_mode:
        focus_instruction = """
- El titular es una pregunta.
- La primera oración debe responder explícitamente esa pregunta.
- No repitas la pregunta.
"""
    else:
        focus_instruction = """
- Explica qué ocurrió.
- Añade solo el contexto mínimo necesario para entender la relevancia.
"""

    prompt = f"""
El siguiente texto corresponde a una noticia.

TITULAR:
{title}

{focus_instruction}

REGLAS EDITORIALES (ESTILO RAYNEWS):

- Usa únicamente información explícita del texto.
- No inventes datos.
- No infieras hechos.
- No agregues opinión ni valoración.
- No uses lenguaje aspiracional o narrativo del medio.
- No uses expresiones como: "momento clave", "principal fuerza", "avance significativo", "se perfila como".
- No copies listados extensos de nombres si no son esenciales.
- Prioriza hechos verificables, cifras y decisiones concretas.
- Añade solo contexto breve si ayuda a entender el hecho.
- Redacción sobria, directa y clara.
- Máximo {MAX_SUMMARY_LENGTH} caracteres.
- Debe terminar en punto.
- Devuelve solo el resumen final.

NOTICIA:
{text}
"""

    try:
        print("🔵 Generando resumen estilo B...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.05,
            max_tokens=350
        )

        summary = clean_text(response.choices[0].message.content.strip())

        # 🔎 Validación
        if (
            len(summary) <= MAX_SUMMARY_LENGTH
            and summary.endswith(".")
            and summary_covers_title(summary, title)
            and not is_low_quality(summary)
        ):
            return summary

        print("⚠ Reintento con mayor foco...")

        retry_prompt = prompt + "\n\nReescribe con mayor precisión y elimina cualquier lenguaje narrativo."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": retry_prompt}],
            temperature=0.02,
            max_tokens=350
        )

        return clean_text(response.choices[0].message.content.strip())

    except Exception as e:
        print("🔴 Error en OpenAI:", e)
        return fallback_summary(text)
