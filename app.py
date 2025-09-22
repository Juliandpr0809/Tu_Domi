from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import math
import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)  # Permitir solicitudes desde el frontend

# Configuración
class Config:
    # APIs Keys (deberías ponerlas en variables de entorno)
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    FUEL_API_KEY = os.getenv('FUEL_API_KEY', '')
    
    # Configuración de vehículos
    VEHICLES = {
        'moto': {
            'label': 'Moto',
            'icon': '🏍️',
            'consumption': 35,  # km/galón
            'base_rate': 2000   # pesos por km
        },
        'carro': {
            'label': 'Carro',
            'icon': '🚗',
            'consumption': 12,
            'base_rate': 2500
        },
        'camioneta': {
            'label': 'Camioneta',
            'icon': '🚙',
            'consumption': 8,
            'base_rate': 3000
        },
        'bicicleta': {
            'label': 'Bicicleta',
            'icon': '🚲',
            'consumption': 0,
            'base_rate': 1500
        }
    }
    
    # Multiplicadores de cilindraje
    ENGINE_MULTIPLIERS = {
        'small': 0.9,    # <1500cc
        'medium': 1.0,   # 1500-2500cc
        'large': 1.3     # >2500cc
    }
    
    # Multiplicadores por hora del día
    TIME_MULTIPLIERS = {
        'peak': 1.5,     # Hora pico
        'normal': 1.0,   # Hora normal
        'valley': 0.8    # Hora valle
    }
    
    # Precio base de gasolina (pesos por galón)
    DEFAULT_FUEL_PRICE = 16000

# Servicios
class LocationService:
    """Servicio para manejar ubicaciones y rutas"""
    
    @staticmethod
    def get_route_info(origin, destination):
        """Obtiene información de ruta usando Google Maps API"""
        if not Config.GOOGLE_MAPS_API_KEY:
            # Modo simulación si no hay API key
            return LocationService._simulate_route(origin, destination)
        
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': origin,
                'destinations': destination,
                'units': 'metric',
                'mode': 'driving',
                'traffic_model': 'best_guess',
                'departure_time': 'now',
                'key': Config.GOOGLE_MAPS_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
                element = data['rows'][0]['elements'][0]
                
                return {
                    'success': True,
                    'distance_km': element['distance']['value'] / 1000,
                    'duration_minutes': element['duration']['value'] / 60,
                    'duration_in_traffic_minutes': element.get('duration_in_traffic', {}).get('value', element['duration']['value']) / 60,
                    'origin_formatted': origin,
                    'destination_formatted': destination
                }
            else:
                return {'success': False, 'error': 'No se pudo calcular la ruta'}
                
        except Exception as e:
            print(f"Error en LocationService: {e}")
            return LocationService._simulate_route(origin, destination)
    
    @staticmethod
    def _simulate_route(origin, destination):
        """Simula datos de ruta para desarrollo"""
        import random
        
        # Generar distancia y tiempo simulados
        distance = round(random.uniform(3, 25), 1)
        base_duration = distance * 3  # 3 minutos por km aprox
        traffic_factor = random.uniform(1.1, 1.8)  # Factor de tráfico
        duration_with_traffic = base_duration * traffic_factor
        
        return {
            'success': True,
            'distance_km': distance,
            'duration_minutes': base_duration,
            'duration_in_traffic_minutes': duration_with_traffic,
            'origin_formatted': origin,
            'destination_formatted': destination,
            'simulated': True
        }

class FuelService:
    """Servicio para obtener precios de combustible"""
    
    @staticmethod
    def get_current_fuel_price():
        """Obtiene el precio actual de la gasolina"""
        # TODO: Integrar con API real de precios de combustible en Colombia
        # Por ahora retorna el precio por defecto
        return {
            'success': True,
            'price_per_gallon': Config.DEFAULT_FUEL_PRICE,
            'last_updated': datetime.now().isoformat(),
            'currency': 'COP'
        }

class CalculationService:
    """Servicio principal para cálculos de domicilio"""
    
    @staticmethod
    def calculate_delivery_cost(form_data):
        """Calcula el costo total del domicilio"""
        try:
            # 1. Obtener información de ruta
            route_info = LocationService.get_route_info(
                form_data['origin'], 
                form_data['destination']
            )
            
            if not route_info['success']:
                return {'success': False, 'error': route_info.get('error', 'Error en cálculo de ruta')}
            
            # 2. Obtener configuración del vehículo
            vehicle = Config.VEHICLES.get(form_data['vehicle_type'])
            if not vehicle:
                return {'success': False, 'error': 'Tipo de vehículo no válido'}
            
            # 3. Calcular componentes del costo
            distance_km = route_info['distance_km']
            
            # Costo base por distancia
            base_cost = distance_km * vehicle['base_rate']
            
            # Costo de combustible
            fuel_cost = CalculationService._calculate_fuel_cost(
                distance_km, 
                vehicle, 
                form_data.get('engine_size', 'medium'),
                form_data.get('fuel_price', Config.DEFAULT_FUEL_PRICE)
            )
            
            # Ajuste por tráfico/hora
            traffic_adjustment = CalculationService._calculate_traffic_adjustment(
                base_cost, 
                form_data['time_of_day']
            )
            
            # Ajuste por peso
            weight_adjustment = CalculationService._calculate_weight_adjustment(
                form_data.get('weight', 0)
            )
            
            # Costo total
            total_cost = base_cost + fuel_cost + traffic_adjustment + weight_adjustment
            
            # Preparar respuesta detallada
            result = {
                'success': True,
                'total_cost': round(total_cost, 0),
                'breakdown': {
                    'base_cost': round(base_cost, 0),
                    'fuel_cost': round(fuel_cost, 0),
                    'traffic_adjustment': round(traffic_adjustment, 0),
                    'weight_adjustment': round(weight_adjustment, 0)
                },
                'route_info': route_info,
                'vehicle_info': vehicle,
                'fuel_consumption': CalculationService._calculate_fuel_consumption(
                    distance_km, 
                    vehicle, 
                    form_data.get('engine_size', 'medium')
                ),
                'calculation_details': {
                    'time_of_day': form_data['time_of_day'],
                    'weight': form_data.get('weight', 0),
                    'fuel_price': form_data.get('fuel_price', Config.DEFAULT_FUEL_PRICE),
                    'calculated_at': datetime.now().isoformat()
                }
            }
            
            return result
            
        except Exception as e:
            print(f"Error en cálculo: {e}")
            return {'success': False, 'error': 'Error interno en el cálculo'}
    
    @staticmethod
    def _calculate_fuel_cost(distance_km, vehicle, engine_size, fuel_price_per_gallon):
        """Calcula el costo de combustible"""
        if vehicle['consumption'] == 0:  # Bicicleta
            return 0
        
        # Aplicar multiplicador de cilindraje
        engine_multiplier = Config.ENGINE_MULTIPLIERS.get(engine_size, 1.0)
        
        # Calcular consumo en galones
        consumption_km_per_gallon = vehicle['consumption'] * engine_multiplier
        gallons_needed = distance_km / consumption_km_per_gallon
        
        # Costo total de combustible
        fuel_cost = gallons_needed * fuel_price_per_gallon
        
        return fuel_cost
    
    @staticmethod
    def _calculate_fuel_consumption(distance_km, vehicle, engine_size):
        """Calcula el consumo de combustible en litros"""
        if vehicle['consumption'] == 0:  # Bicicleta
            return 0
        
        engine_multiplier = Config.ENGINE_MULTIPLIERS.get(engine_size, 1.0)
        consumption_km_per_gallon = vehicle['consumption'] * engine_multiplier
        gallons_needed = distance_km / consumption_km_per_gallon
        
        # Convertir galones a litros (1 galón = 3.785 litros)
        liters_needed = gallons_needed * 3.785
        
        return round(liters_needed, 2)
    
    @staticmethod
    def _calculate_traffic_adjustment(base_cost, time_of_day):
        """Calcula el ajuste por tráfico según la hora"""
        multiplier = Config.TIME_MULTIPLIERS.get(time_of_day, 1.0)
        adjustment = base_cost * (multiplier - 1.0)
        return adjustment
    
    @staticmethod
    def _calculate_weight_adjustment(weight):
        """Calcula el ajuste por peso extra"""
        if weight > 5:
            extra_weight = weight - 5
            return extra_weight * 500  # $500 por cada kg extra
        return 0

# Rutas de la aplicación
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/calculate', methods=['POST'])
def calculate_delivery():
    """Endpoint principal para calcular costo de domicilio"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['origin', 'destination', 'vehicle_type', 'time_of_day']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }), 400
        
        # Realizar cálculo
        result = CalculationService.calculate_delivery_cost(data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        print(f"Error en /api/calculate: {e}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@app.route('/api/fuel-price', methods=['GET'])
def get_fuel_price():
    """Endpoint para obtener precio actual del combustible"""
    try:
        result = FuelService.get_current_fuel_price()
        return jsonify(result), 200
    except Exception as e:
        print(f"Error en /api/fuel-price: {e}")
        return jsonify({
            'success': False,
            'error': 'Error al obtener precio de combustible'
        }), 500

@app.route('/api/validate-address', methods=['POST'])
def validate_address():
    """Endpoint para validar direcciones"""
    try:
        data = request.get_json()
        address = data.get('address', '')
        
        if not address:
            return jsonify({
                'success': False,
                'error': 'Dirección no proporcionada'
            }), 400

        # Aquí se podría agregar lógica de validación de dirección
        return jsonify({
            'success': True,
            'message': 'Dirección válida'
        }), 200

    except Exception as e:
        print(f"Error en /api/validate-address: {e}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500
    
if __name__ == '__main__':
    app.run(debug=True)