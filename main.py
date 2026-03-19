import json
import os # <--- NUEVO: Para leer el archivo de sesión
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

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
            # Esto evita extraer datos antes de que la página termine de cargar
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
                            // Sacamos el texto del botón (ej: agregaProductoAlCarrito('02AB005', 1); )
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
            
            return {
                "status": "success", 
                "query": query, 
                "total_encontrados": len(datos_extraidos),
                "data": datos_extraidos
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            browser.close()

# 1. Creamos el "molde" de lo que el Agente de IA nos tiene que enviar
class ProductoCarrito(BaseModel):
    codigo_interno: str
    cantidad: int = 1 # Si el agente no dice cuántos, por defecto será 1

# 2. Creamos el nuevo endpoint POST
@app.post("/api/v1/carrito/agregar")
def agregar_al_carrito(item: ProductoCarrito):
    # 1. Verificamos que el gafete exista
    if not os.path.exists("state.json"):
        raise HTTPException(status_code=401, detail="No hay sesión activa. Por favor, ejecuta el /api/v1/auth/login primero.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 2. ¡LA MAGIA! Abrimos el navegador inyectándole las cookies del archivo
        context = browser.new_context(storage_state="state.json")
        page = context.new_page()
        
        try:
            # 3. Al entrar a Rolcar, la página ya nos reconocerá como usuarios logueados
            page.goto("http://ecommerce.rolcar.com.mx:8080/ecommerce/")
            page.wait_for_load_state('networkidle')
            
            # 4. Agregamos al carrito
            comando_js = f"agregaProductoAlCarrito('{item.codigo_interno}', {item.cantidad});"
            page.evaluate(comando_js)
            page.wait_for_timeout(2000) 
            
            return {
                "status": "success", 
                "mensaje": f"Se agregaron {item.cantidad} pieza(s) del producto {item.codigo_interno} al carrito real.",
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            browser.close()

@app.post("/api/v1/auth/login")
def iniciar_sesion(datos: LoginData):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Creamos un "Contexto" (es como abrir una ventana de incógnito nueva)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 1. Vamos a la página principal
            page.goto("http://ecommerce.rolcar.com.mx:8080/ecommerce/")
            page.wait_for_load_state('networkidle')
            
            # 2. Damos clic en el texto para abrir la ventanita
            page.get_by_text("Inicia Sesión").click()
            
            # 3. Esperamos a que el campo de usuario de la ventanita sea visible
            page.wait_for_selector("#usuario", state="visible", timeout=10000)
            
            # 4. Llenamos los datos usando los IDs que descubriste
            page.locator("#usuario").fill(datos.usuario) 
            page.locator("#password").fill(datos.password)
            
            # 5. TRUCO NINJA: Presionamos la tecla Enter estando en el campo de contraseña
            page.locator("#password").press("Enter")
            
            # 6. Esperamos a que la página procese el login y recargue
            page.wait_for_load_state('networkidle')
            
            # 7. Guardamos el gafete (state.json)
            context.storage_state(path="state.json")
            
            return {"status": "success", "mensaje": "Sesión iniciada y gafete (state.json) creado exitosamente."}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            browser.close()