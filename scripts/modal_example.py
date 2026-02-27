"""
Procesador de Datos con IA - Ejemplo Modal

Script de ejemplo para ejecutarse en Modal.com como función serverless.
Procesa datos desde un archivo y genera resultados usando un modelo de IA.

Uso:
    modal deploy modal_example.py
    
    # Invocar vía web
    curl -X POST https://tu-usuario--data-processor-api-process.modal.run \\
      -H "Content-Type: application/json" \\
      -d '{"input_data": "texto a procesar", "model": "gpt-4"}'
"""

import modal
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# ============================================================================
# CONFIGURACIÓN DE MODAL
# ============================================================================

# Crear app de Modal
app = modal.App("data-processor")

# Definir imagen con dependencias necesarias
image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "openai==1.54.0",
    "pydantic==2.12.5",
    "fastapi==0.115.6",
    "uvicorn==0.40.0"
)

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class ProcessRequest(BaseModel):
    """Modelo para la solicitud de procesamiento."""
    input_data: str = Field(description="Datos de entrada a procesar")
    model: str = Field(default="gpt-4", description="Modelo de IA a utilizar")
    temperature: float = Field(default=0.7, description="Temperatura del modelo")


class ProcessResult(BaseModel):
    """Modelo para el resultado del procesamiento."""
    output: str = Field(description="Resultado procesado")
    tokens_used: int = Field(description="Tokens utilizados")
    model: str = Field(description="Modelo utilizado")


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def validate_input(data: str) -> bool:
    """
    Valida que los datos de entrada sean correctos.
    
    Args:
        data: Datos a validar
        
    Returns:
        bool: True si los datos son válidos
    """
    if not data or len(data.strip()) == 0:
        raise ValueError("Los datos de entrada no pueden estar vacíos")
    
    if len(data) > 10000:
        raise ValueError("Los datos de entrada exceden el límite de 10000 caracteres")
    
    return True


def process_with_ai(input_text: str, model: str, temperature: float, api_key: str) -> ProcessResult:
    """
    Procesa el texto usando un modelo de IA (OpenAI compatible).
    
    Args:
        input_text: Texto a procesar
        model: Nombre del modelo a usar
        temperature: Temperatura del modelo
        api_key: API key del servicio de IA
        
    Returns:
        ProcessResult: Resultado del procesamiento
    """
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    
    # Prompt de ejemplo - personalízalo según tu caso de uso
    prompt = f"""Analiza el siguiente texto y proporciona un resumen estructurado:

Texto: {input_text}

Por favor proporciona:
1. Resumen en 2-3 líneas
2. Puntos clave (máximo 5)
3. Tono del texto (formal/informal/técnico/etc)
"""
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Eres un asistente que analiza y resume textos de manera estructurada."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )
    
    return ProcessResult(
        output=response.choices[0].message.content,
        tokens_used=response.usage.total_tokens,
        model=model
    )


def save_result_to_file(result: ProcessResult, output_path: str) -> str:
    """
    Guarda el resultado en un archivo JSON.
    
    Args:
        result: Resultado a guardar
        output_path: Ruta donde guardar el archivo
        
    Returns:
        str: Ruta del archivo guardado
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_path}/result_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
    
    return filename


# ============================================================================
# FUNCIÓN PRINCIPAL DE MODAL
# ============================================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("api-keys"),  # Debe contener OPENAI_API_KEY
    ],
    timeout=300,  # 5 minutos
    retries=2  # Reintentos en caso de fallo
)
def process_data(
    input_data: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    save_output: bool = False
) -> Dict:
    """
    Procesa datos de entrada usando IA y retorna el resultado.
    
    Args:
        input_data: Texto o datos a procesar
        model: Modelo de IA a utilizar
        temperature: Temperatura del modelo (0.0 - 2.0)
        save_output: Si True, guarda el resultado en un archivo
    
    Returns:
        dict: Resultado con status, data y message
    """
    try:
        print(f"🚀 Iniciando procesamiento con modelo {model}...")
        print(f"📊 Longitud de entrada: {len(input_data)} caracteres")
        
        # Validar entrada
        validate_input(input_data)
        print("  ✅ Validación de entrada exitosa")
        
        # Obtener API key desde secretos de Modal
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "data": None,
                "message": "No se encontró OPENAI_API_KEY en los secretos de Modal"
            }
        
        # Procesar con IA
        print("🤖 Procesando con IA...")
        result = process_with_ai(input_data, model, temperature, api_key)
        print(f"  ✅ Procesamiento exitoso - {result.tokens_used} tokens usados")
        
        # Guardar resultado si se solicita
        output_file = None
        if save_output:
            print("💾 Guardando resultado...")
            output_file = save_result_to_file(result, "/tmp")
            print(f"  ✅ Resultado guardado en {output_file}")
        
        return {
            "status": "success",
            "data": {
                "output": result.output,
                "tokens_used": result.tokens_used,
                "model_used": result.model,
                "output_file": output_file,
                "timestamp": datetime.now().isoformat()
            },
            "message": f"✅ Procesamiento completado exitosamente con {result.tokens_used} tokens"
        }
    
    except ValueError as e:
        print(f"❌ Error de validación: {e}")
        return {
            "status": "error",
            "data": None,
            "message": f"Error de validación: {str(e)}"
        }
    
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return {
            "status": "error",
            "data": None,
            "message": f"Error durante el procesamiento: {str(e)}"
        }


# ============================================================================
# WEB ENDPOINT (API REST)
# ============================================================================

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("api-keys")]
)
@modal.asgi_app()
def api_process():
    """
    Endpoint HTTP para procesar datos vía API REST.
    """
    from fastapi import FastAPI, HTTPException
    
    web_app = FastAPI(
        title="Data Processor API",
        description="API para procesar datos con IA usando Modal",
        version="1.0.0"
    )
    
    @web_app.post("/process")
    async def process_endpoint(request: ProcessRequest):
        """
        Procesa datos de entrada usando IA.
        
        Ejemplo de uso:
            curl -X POST https://tu-usuario--data-processor-api-process.modal.run/process \\
              -H "Content-Type: application/json" \\
              -d '{
                "input_data": "Este es un texto de ejemplo para procesar",
                "model": "gpt-4",
                "temperature": 0.7
              }'
        """
        try:
            result = process_data.local(
                input_data=request.input_data,
                model=request.model,
                temperature=request.temperature,
                save_output=False
            )
            
            if result["status"] == "error":
                raise HTTPException(status_code=400, detail=result["message"])
            
            return result
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @web_app.get("/health")
    async def health_check():
        """Endpoint de health check."""
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    return web_app


# ============================================================================
# FUNCIÓN LOCAL PARA TESTING
# ============================================================================

@app.local_entrypoint()
def main():
    """
    Ejecutar localmente para testing.
    
    Uso: modal run modal_example.py
    """
    print("🧪 Ejecutando test local...\n")
    
    test_input = """
    La inteligencia artificial está transformando múltiples industrias.
    Desde la medicina hasta las finanzas, los modelos de IA están ayudando
    a resolver problemas complejos y automatizar tareas repetitivas.
    """
    
    result = process_data.remote(
        input_data=test_input.strip(),
        model="gpt-4",
        temperature=0.7,
        save_output=False
    )
    
    print("\n" + "="*80)
    print("RESULTADO DEL TEST")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("="*80)