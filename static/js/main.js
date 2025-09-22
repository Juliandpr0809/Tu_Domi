// Datos de configuración
const vehicleTypes = {
  moto: { label: "Moto", icon: "🏍️", consumption: 35 },
  carro: { label: "Carro", icon: "🚗", consumption: 12 },
  camioneta: { label: "Camioneta", icon: "🚙", consumption: 8 },
  bicicleta: { label: "Bicicleta", icon: "🚲", consumption: 0 },
}

const engineSizes = {
  small: { label: "Pequeño (<1500cc)", multiplier: 0.9 },
  medium: { label: "Mediano (1500-2500cc)", multiplier: 1.0 },
  large: { label: "Grande (>2500cc)", multiplier: 1.3 },
}

const timeSlots = {
  peak: { label: "Hora Pico (7-9 AM, 5-7 PM)", multiplier: 1.5 },
  normal: { label: "Hora Normal (9 AM-5 PM)", multiplier: 1.0 },
  valley: { label: "Hora Valle (7 PM-7 AM)", multiplier: 0.8 },
}

// Variables globales
let isCalculating = false
const lucide = window.lucide // Declare the lucide variable

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
  // Inicializar iconos de Lucide
  lucide.createIcons()

  // Event listeners
  setupEventListeners()
})

function setupEventListeners() {
  const form = document.getElementById("deliveryForm")
  const vehicleSelect = document.getElementById("vehicleType")

  // Manejar envío del formulario
  form.addEventListener("submit", handleFormSubmit)

  // Mostrar/ocultar campo de cilindraje según el vehículo
  vehicleSelect.addEventListener("change", handleVehicleChange)
}

function handleVehicleChange(e) {
  const engineSizeGroup = document.getElementById("engineSizeGroup")
  const engineSizeSelect = document.getElementById("engineSize")

  if (e.target.value === "bicicleta" || e.target.value === "") {
    engineSizeGroup.style.display = "none"
    engineSizeSelect.value = ""
  } else {
    engineSizeGroup.style.display = "block"
  }
}

function handleFormSubmit(e) {
  e.preventDefault()

  if (isCalculating) return

  const formData = getFormData()
  if (!validateFormData(formData)) return

  calculateDelivery(formData)
}

function getFormData() {
  return {
    origin: document.getElementById("origin").value.trim(),
    destination: document.getElementById("destination").value.trim(),
    vehicleType: document.getElementById("vehicleType").value,
    engineSize: document.getElementById("engineSize").value,
    fuelPrice: Number.parseFloat(document.getElementById("fuelPrice").value) || 15000,
    timeOfDay: document.getElementById("timeOfDay").value,
    weight: Number.parseFloat(document.getElementById("weight").value) || 0,
  }
}

function validateFormData(data) {
  const required = ["origin", "destination", "vehicleType", "timeOfDay"]

  for (const field of required) {
    if (!data[field]) {
      alert(`Por favor completa el campo: ${field}`)
      return false
    }
  }

  if (data.vehicleType !== "bicicleta" && !data.engineSize) {
    alert("Por favor selecciona el cilindraje del vehículo")
    return false
  }

  return true
}

function calculateDelivery(formData) {
  setCalculatingState(true)

  // Simular cálculo con delay (en una app real sería una llamada a API)
  setTimeout(() => {
    const result = performCalculation(formData)
    displayResults(result)
    setCalculatingState(false)
  }, 2000)
}

function performCalculation(formData) {
  const vehicle = vehicleTypes[formData.vehicleType]
  const engine = engineSizes[formData.engineSize] || { multiplier: 1.0 }
  const timeSlot = timeSlots[formData.timeOfDay]

  // Distancia simulada (en una app real vendría de una API de mapas)
  const distance = Math.random() * 20 + 5 // 5-25 km

  // Cálculo de consumo de combustible
  const baseConsumption = vehicle.consumption || 12
  const engineMultiplier = engine.multiplier
  const fuelConsumption = (distance / baseConsumption) * engineMultiplier

  // Costo de combustible (convertir galón a litros)
  const fuelCost = fuelConsumption * (formData.fuelPrice / 3.785)

  // Tarifa base
  const baseFare = distance * 2500 // $2500 por km base

  // Ajuste por tráfico
  const trafficMultiplier = timeSlot.multiplier
  const trafficAdjustment = baseFare * (trafficMultiplier - 1)

  // Ajuste por peso
  const weightAdjustment = formData.weight > 5 ? (formData.weight - 5) * 500 : 0

  const total = fuelCost + baseFare + trafficAdjustment + weightAdjustment

  return {
    fuelConsumption,
    baseFare,
    trafficAdjustment,
    weightAdjustment,
    total,
    distance,
    fuelCost,
    formData,
  }
}

function setCalculatingState(calculating) {
  isCalculating = calculating
  const btn = document.getElementById("calculateBtn")
  const spinner = btn.querySelector(".loading-spinner")
  const text = btn.querySelector("span")

  if (calculating) {
    btn.disabled = true
    spinner.style.display = "block"
    text.textContent = "Calculando..."
  } else {
    btn.disabled = false
    spinner.style.display = "none"
    text.textContent = "Calcular Costo del Domicilio"
  }
}

function displayResults(result) {
  const container = document.getElementById("resultsContainer")

  container.innerHTML = `
        <div class="results-display show">
            <div class="total-cost">
                <div class="total-amount">$${result.total.toLocaleString("es-CO")}</div>
                <div class="total-label">Costo total del domicilio</div>
                <div class="distance-info">Distancia estimada: ${result.distance.toFixed(1)} km</div>
            </div>
            
            <div class="breakdown">
                <h4>Desglose de Costos:</h4>
                
                <div class="breakdown-item">
                    <div class="breakdown-left">
                        <i data-lucide="fuel"></i>
                        <span>Consumo de Combustible</span>
                    </div>
                    <div class="breakdown-right">
                        <div class="breakdown-amount">$${result.fuelCost.toLocaleString("es-CO")}</div>
                        <div class="breakdown-detail">${result.fuelConsumption.toFixed(2)} litros</div>
                    </div>
                </div>
                
                <div class="breakdown-item">
                    <div class="breakdown-left">
                        <i data-lucide="map-pin"></i>
                        <span>Tarifa Base por Distancia</span>
                    </div>
                    <div class="breakdown-right">
                        <div class="breakdown-amount">$${result.baseFare.toLocaleString("es-CO")}</div>
                        <div class="breakdown-detail">$2,500 por km</div>
                    </div>
                </div>
                
                ${
                  result.trafficAdjustment !== 0
                    ? `
                <div class="breakdown-item">
                    <div class="breakdown-left">
                        <i data-lucide="clock"></i>
                        <span>Ajuste por Tráfico</span>
                    </div>
                    <div class="breakdown-right">
                        <div class="breakdown-amount ${result.trafficAdjustment > 0 ? "positive" : "negative"}">
                            ${result.trafficAdjustment > 0 ? "+" : ""}$${result.trafficAdjustment.toLocaleString("es-CO")}
                        </div>
                        <div class="breakdown-detail">
                            ${result.trafficAdjustment > 0 ? "Hora pico" : "Hora valle"}
                        </div>
                    </div>
                </div>
                `
                    : ""
                }
                
                ${
                  result.weightAdjustment > 0
                    ? `
                <div class="breakdown-item">
                    <div class="breakdown-left">
                        <i data-lucide="package"></i>
                        <span>Ajuste por Peso Extra</span>
                    </div>
                    <div class="breakdown-right">
                        <div class="breakdown-amount positive">
                            +$${result.weightAdjustment.toLocaleString("es-CO")}
                        </div>
                        <div class="breakdown-detail">Peso > 5kg</div>
                    </div>
                </div>
                `
                    : ""
                }
            </div>
            
            <div class="tips-box">
                <h5>💡 Consejos para Ahorrar:</h5>
                <ul>
                    <li>• Envía en hora valle para reducir costos hasta 20%</li>
                    <li>• Agrupa varios paquetes en un solo envío</li>
                    <li>• Considera vehículos más eficientes para distancias largas</li>
                    ${result.weightAdjustment > 0 ? "<li>• Reduce el peso del paquete para evitar cargos extra</li>" : ""}
                </ul>
            </div>
            
            <button class="new-calculation-btn" onclick="resetCalculation()">
                Calcular Nuevo Envío
            </button>
        </div>
    `

  // Reinicializar iconos de Lucide para los nuevos elementos
  lucide.createIcons()
}

function resetCalculation() {
  const container = document.getElementById("resultsContainer")

  container.innerHTML = `
        <div class="empty-state">
            <i data-lucide="calculator" class="empty-icon"></i>
            <h3>Listo para Calcular</h3>
            <p>Completa el formulario de la izquierda y haz clic en "Calcular Costo" para ver el desglose detallado de tu domicilio.</p>
            
            <div class="info-box">
                <h4>Factores que Influyen en el Precio:</h4>
                <div class="factors-grid">
                    <div>• Distancia del recorrido</div>
                    <div>• Tipo de vehículo</div>
                    <div>• Consumo de combustible</div>
                    <div>• Condiciones de tráfico</div>
                    <div>• Peso del paquete</div>
                    <div>• Precio actual del combustible</div>
                </div>
            </div>
        </div>
    `

  // Reinicializar iconos
  lucide.createIcons()
}

// Función para formatear números como moneda colombiana
Number.prototype.toLocaleString = function (locale) {
  return this.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")
}
