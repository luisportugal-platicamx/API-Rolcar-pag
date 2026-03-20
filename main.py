import json
import os # <--- NUEVO: Para leer el archivo de sesión
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError # <--- NUEVO: Importamos el error de Timeout

app = FastAPI(title="API Agente Rolcar")

# --- MODELOS DE DATOS ---
class LoginData(BaseModel):
    usuario: str
    password: str

class ProductoCarrito(BaseModel):
    codigo_interno: str
    cantidad: int = 1

@app.get("/api/v1/productos/buscar")
def buscar_productos(query: str):
    with sync_playwright() as p:
        # Bucle para permitir máximo 2 intentos (0 y 1)
        for intento in range(2):
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # 1. Entramos a la página principal
                page.goto("http://ecommerce.rolcar.com.mx:8080/ecommerce/")
                page.wait_for_load_state('networkidle')
                
                # 2. Hacemos la búsqueda
                page.locator("#nxt-search").fill(query)
                page.locator("#nxt-search").press("Enter")
                
                # 3. Esperamos específicamente a que las tarjetas de producto existan
                page.wait_for_selector(".product_item", timeout=15000)
                
                # 4. EXTRACCIÓN CON CABALLO DE TROYA (Texto plano)
                javascript_puro = """
                () => {
                    let resultados = [];
                    // 1. Buscamos SOLO las tarjetas de los productos (ignoramos la paginación)
                    let tarjetas = document.querySelectorAll('.product_item');
                    
                    // 2. Revisamos tarjeta por tarjeta
                    tarjetas.forEach(tarjeta => {
                        let nombreEl = tarjeta.querySelector('.m_bottom_0 a');
                        let codigoEl = tarjeta.querySelector('.f_size_large b');
                        let precioEl = tarjeta.querySelector('.text_red.f_size_large');
                        
                        // Buscamos el botón de agregar para robarle el código interno
                        let botonAgregar = tarjeta.querySelector('a[onclick*="agregaProductoAlCarrito"]');
                        
                        if (nombreEl && precioEl) {
                            let codigo_interno = "";
                            if (botonAgregar) {
                                // Sacamos el texto del botón
                                let onclickTexto = botonAgregar.getAttribute('onclick');
                                // Magia oscura (RegEx) para extraer solo lo que está entre comillas simples
                                let match = onclickTexto.match(/'([^']+)'/);
                                if (match) codigo_interno = match[1];
                            }
                            
                            resultados.push({
                                "nombre": nombreEl.innerText.trim(),
                                "codigo_fabricante": codigoEl ? codigoEl.innerText.trim() : "",
                                "codigo_interno": codigo_interno, // <-- ¡LA LLAVE MAESTRA!
                                "precio": precioEl.innerText.trim()
                            });
                        }
                    });
                    
                    return JSON.stringify(resultados);
                }
                """
                
                # 5. Ejecutamos y recibimos TEXTO
                datos_crudos = page.evaluate(javascript_puro)
                
                # 6. Transformamos el texto sano de vuelta a una lista de Python
                if datos_crudos:
                    datos_extraidos = json.loads(datos_crudos)
                else:
                    datos_extraidos = []
                
                # 7. Si todo salió bien, cerramos el navegador y regresamos la data
                browser.close()
                return {
                    "status": "success", 
                    "query": query, 
                    "total_encontrados": len(datos_extraidos),
                    "data": datos_extraidos
                }
                
            except PlaywrightTimeoutError as e:
                browser.close() # Cerramos el navegador fallido para no dejar procesos huérfanos
                if intento == 0:
                    print(f"Timeout detectado al buscar '{query}'. Reintentando una vez más...")
                    continue # Vuelve al inicio del 'for' e intenta de nuevo
                else:
                    # Si ya es el segundo intento y vuelve a dar timeout, lanzamos un error 504
                    raise HTTPException(status_code=504, detail="El servidor de Rolcar tardó demasiado en responder tras 2 intentos.")
                    
            except Exception as e:
                # Si es cualquier otro error que no sea Timeout, fallamos de inmediato
                browser.close()
                raise HTTPException(status_code=500, detail=str(e))

# ... [El resto de tu código para /api/v1/carrito/agregar y /api/v1/auth/login permanece exactamente igual] ...
