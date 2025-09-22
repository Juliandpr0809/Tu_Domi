# services.py - Servicios para APIs reales
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import redis
from flask import current_app

class APICache:
    """Sistema de cache para optimizar llamadas a APIs"""
    
    def __init__(self):
        self.redis_client = None
        try:
            # Intentar conectar a Redis para cache
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=os.getenv('REDIS_PORT', 6379),
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
        except:
            # Usar cache en memoria si Redis no está disponible
            self.memory_cache = {}
            self.cache_timestamps = {}
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[str]:
        """Obtiene valor del cache"""
        try:
            if self.redis_client:
                return self.redis_client.get(key)
            else:
                # Cache en memoria
                if key in self.memory_cache:
                    timestamp = self.cache_timestamps.get(key, 0)
                    if datetime.now().timestamp() - timestamp < ttl_seconds:
                        return self.memory_cache[key]
                    else:
                        # Cache expirado
                        del self.memory_cache[key]
                        del self.cache_timestamps[key]
                return None
        except:
            return None
    
    def set(self, key: str, value: str, ttl_seconds: int = 300):
        """Guarda valor en cache"""
        try:
            if self.redis_client:
                self.redis_client.setex(key, ttl_seconds, value)
            else:
                # Cache en memoria
                self.memory_cache[key] = value
                self.cache_timestamps[key] = datetime.now().timestamp()
        except:
            pass

# Instancia global del cache
api_cache = APICache()

class GoogleMapsService:
    """Servicio completo para Google Maps APIs"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def get_detailed_route_info(self, origin: str, destination: str) -> Dict:
        """Obtiene información detallada de ruta con tráfico en tiempo real"""
        if not self.api_key:
            return self._simulate_detailed_route(origin, destination)
        
        # Clave para cache
        cache_key = f"route:{hash(f'{origin}:{destination}')}"
        cached_result = api_cache.get(cache_key, ttl_seconds=300)  # 5 minutos
        
        if cached_result:
            return json.loads(cached_result)
        
        try:
            # 1. Geocodificar direcciones
            origin_coords = self._geocode_address(origin)
            destination_coords = self._geocode_address(destination)
            
            if not origin_coords['success'] or not destination_coords['success']:
                return {'success': False, 'error': 'No se pudieron geocodificar las direcciones'}
            
            # 2. Obtener información de ruta con tráfico
            route_info = self._get_distance_matrix_with_traffic(
                origin_coords['formatted_address'], 
                destination_coords['formatted_address']
            )
            
            if not route_info['success']:
                return route_info
            
            # 3. Obtener ruta detallada con waypoints
            detailed_route = self._get_directions(
                origin_coords['coordinates'], 
                destination_coords['coordinates']
            )
            
            # 4. Combinar toda la información
            result = {
                'success': True,
                'distance_km': route_info['distance_km'],
                'duration_minutes': route_info['duration_minutes'],
                'duration_in_traffic_minutes': route_info['duration_in_traffic_minutes'],
                'traffic_delay_minutes': route_info['duration_in_traffic_minutes'] - route_info['duration_minutes'],
                'origin': {
                    'address': origin,
                    'formatted_address': origin_coords['formatted_address'],
                    'coordinates': origin_coords['coordinates']
                },
                'destination': {
                    'address': destination,
                    'formatted_address': destination_coords['formatted_address'],
                    'coordinates': destination_coords['coordinates']
                },
                'route_quality': self._assess_route_quality(route_info, detailed_route),
                'traffic_conditions': self._analyze_traffic_conditions(route_info),
                'alternative_routes': detailed_route.get('alternative_routes', []),
                'calculated_at': datetime.now().isoformat()
            }
            
            # Guardar en cache
            api_cache.set(cache_key, json.dumps(result), ttl_seconds=300)
            
            return result
            
        except Exception as e:
            print(f"Error en GoogleMapsService: {e}")
            return self._simulate_detailed_route(origin, destination)
    
    def _geocode_address(self, address: str) -> Dict:
        """Geocodifica una dirección"""
        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                'address': address,
                'key': self.api_key,
                'language': 'es',
                'region': 'co'  # Colombia
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and len(data['results']) > 0:
                result = data['results'][0]
                location = result['geometry']['location']
                
                return {
                    'success': True,
                    'formatted_address': result['formatted_address'],
                    'coordinates': {'lat': location['lat'], 'lng': location['lng']},
                    'place_id': result['place_id']
                }
            else:
                return {'success': False, 'error': f'No se encontró la dirección: {address}'}
                
        except Exception as e:
            print(f"Error en geocodificación: {e}")
            return {'success': False, 'error': 'Error en geocodificación'}
    
    def _get_distance_matrix_with_traffic(self, origin: str, destination: str) -> Dict:
        """Obtiene matriz de distancia con información de tráfico"""
        try:
            url = f"{self.base_url}/distancematrix/json"
            params = {
                'origins': origin,
                'destinations': destination,
                'units': 'metric',
                'mode': 'driving',
                'traffic_model': 'best_guess',
                'departure_time': 'now',
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
                element = data['rows'][0]['elements'][0]
                
                duration_in_traffic = element.get('duration_in_traffic', element['duration'])
                
                return {
                    'success': True,
                    'distance_km': element['distance']['value'] / 1000,
                    'distance_text': element['distance']['text'],
                    'duration_minutes': element['duration']['value'] / 60,
                    'duration_text': element['duration']['text'],
                    'duration_in_traffic_minutes': duration_in_traffic['value'] / 60,
                    'duration_in_traffic_text': duration_in_traffic['text']
                }
            else:
                error_msg = data['rows'][0]['elements'][0].get('status', 'Error desconocido')
                return {'success': False, 'error': f'Error en cálculo de ruta: {error_msg}'}
                
        except Exception as e:
            print(f"Error en distance matrix: {e}")
            return {'success': False, 'error': 'Error al calcular distancia'}
    
    def _get_directions(self, origin_coords: Dict, destination_coords: Dict) -> Dict:
        """Obtiene direcciones detalladas con rutas alternativas"""
        try:
            url = f"{self.base_url}/directions/json"
            params = {
                'origin': f"{origin_coords['lat']},{origin_coords['lng']}",
                'destination': f"{destination_coords['lat']},{destination_coords['lng']}",
                'mode': 'driving',
                'alternatives': 'true',
                'traffic_model': 'best_guess',
                'departure_time': 'now',
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data['status'] == 'OK':
                return {
                    'success': True,
                    'routes': data['routes'],
                    'alternative_routes': len(data['routes']) - 1 if len(data['routes']) > 1 else 0
                }
            else:
                return {'success': False, 'error': f'Error en direcciones: {data["status"]}'}
                
        except Exception as e:
            print(f"Error en directions: {e}")
            return {'success': False, 'error': 'Error al obtener direcciones'}
    
    def _assess_route_quality(self, route_info: Dict, detailed_route: Dict) -> str:
        """Evalúa la calidad de la ruta basada en tráfico"""
        if not route_info.get('success'):
            return 'unknown'
        
        traffic_delay = route_info.get('duration_in_traffic_minutes', 0) - route_info.get('duration_minutes', 0)
        delay_percentage = (traffic_delay / route_info.get('duration_minutes', 1)) * 100
        
        if delay_percentage < 10:
            return 'excellent'
        elif delay_percentage < 25:
            return 'good'
        elif delay_percentage < 50:
            return 'moderate'
        else:
            return 'poor'
    
    def _analyze_traffic_conditions(self, route_info: Dict) -> Dict:
        """Analiza las condiciones de tráfico"""
        traffic_delay = route_info.get('duration_in_traffic_minutes', 0) - route_info.get('duration_minutes', 0)
        
        if traffic_delay <= 2:
            condition = 'light'
            severity = 'low'
        elif traffic_delay <= 10:
            condition = 'moderate'
            severity = 'medium'
        else:
            condition = 'heavy'
            severity = 'high'
        
        return {
            'condition': condition,
            'severity': severity,
            'delay_minutes': round(traffic_delay, 1),
            'impact_factor': min(traffic_delay / 30, 1.0)  # Factor de 0 a 1
        }
    
    def _simulate_detailed_route(self, origin: str, destination: str) -> Dict:
        """Simula datos detallados para desarrollo"""
        import random
        
        distance = round(random.uniform(3, 25), 1)
        base_duration = distance * 2.5 + random.uniform(-5, 10)
        traffic_multiplier = random.uniform(1.1, 2.0)
        duration_with_traffic = base_duration * traffic_multiplier
        
        traffic_delay = duration_with_traffic - base_duration
        
        return {
            'success': True,
            'distance_km': distance,
            'duration_minutes': base_duration,
            'duration_in_traffic_minutes': duration_with_traffic,
            'traffic_delay_minutes': traffic_delay,
            'origin': {
                'address': origin,
                'formatted_address': f"{origin}, Colombia",
                'coordinates': {'lat': 10.9639 + random.uniform(-0.1, 0.1), 
                              'lng': -74.7964 + random.uniform(-0.1, 0.1)}
            },
            'destination': {
                'address': destination,
                'formatted_address': f"{destination}, Colombia", 
                'coordinates': {'lat': 10.9639 + random.uniform(-0.1, 0.1),
                              'lng': -74.7964 + random.uniform(-0.1, 0.1)}
            },
            'route_quality': random.choice(['excellent', 'good', 'moderate', 'poor']),
            'traffic_conditions': {
                'condition': random.choice(['light', 'moderate', 'heavy']),
                'severity': random.choice(['low', 'medium', 'high']),
                'delay_minutes': traffic_delay,
                'impact_factor': min(traffic_delay / 30, 1.0)
            },
            'alternative_routes': random.randint(0, 3),
            'calculated_at': datetime.now().isoformat(),
            'simulated': True
        }

class ColombiaFuelService:
    """Servicio para obtener precios reales de combustible en Colombia"""
    
    def __init__(self):
        self.base_urls = [
            "https://www.minenergia.gov.co/",  # Ministerio de Energía
            "https://www.sicom.gov.co/",       # SICOM
        ]
    
    def get_current_fuel_prices(self, city: str = "bogota") -> Dict:
        """Obtiene precios actuales de combustible por ciudad"""
        cache_key = f"fuel_prices:{city.lower()}"
        cached_result = api_cache.get(cache_key, ttl_seconds=3600)  # 1 hora
        
        if cached_result:
            return json.loads(cached_result)
        
        try:
            # Intentar obtener datos reales
            real_prices = self._scrape_official_prices(city)
            
            if real_prices['success']:
                api_cache.set(cache_key, json.dumps(real_prices), ttl_seconds=3600)
                return real_prices
            else:
                # Fallback a precios estimados actualizados
                return self._get_estimated_prices(city)
                
        except Exception as e:
            print(f"Error obteniendo precios de combustible: {e}")
            return self._get_estimated_prices(city)
    
    def _scrape_official_prices(self, city: str) -> Dict:
        """Intenta obtener precios oficiales (implementar según fuentes disponibles)"""
        # TODO: Implementar scraping de fuentes oficiales
        # Por ahora retorna datos simulados realistas
        
        import random
        
        # Precios base promedio en Colombia (2024)
        base_prices = {
            'bogota': 15200,
            'medellin': 15100,
            'cali': 15300,
            'barranquilla': 15250,
            'cartagena': 15280,
        }
        
        base_price = base_prices.get(city.lower(), 15200)
        
        # Simular variación diaria pequeña
        variation = random.uniform(-200, 200)
        current_price = base_price + variation
        
        return {
            'success': True,
            'city': city.title(),
            'prices': {
                'corriente': round(current_price, 0),
                'extra': round(current_price + 500, 0),
                'diesel': round(current_price - 1000, 0)
            },
            'currency': 'COP',
            'unit': 'galón',
            'last_updated': datetime.now().isoformat(),
            'source': 'estimated',
            'next_update': (datetime.now() + timedelta(hours=1)).isoformat()
        }
    
    def _get_estimated_prices(self, city: str) -> Dict:
        """Obtiene precios estimados cuando no hay datos oficiales"""
        return self._scrape_official_prices(city)

class TrafficAnalysisService:
    """Servicio avanzado para análisis de tráfico"""
    
    def __init__(self):
        self.maps_service = GoogleMapsService()
    
    def get_traffic_analysis(self, origin: str, destination: str, 
                           departure_time: Optional[datetime] = None) -> Dict:
        """Análisis completo de tráfico para una ruta"""
        try:
            if not departure_time:
                departure_time = datetime.now()
            
            # Obtener datos de ruta
            route_data = self.maps_service.get_detailed_route_info(origin, destination)
            
            if not route_data['success']:
                return route_data
            
            # Análisis por horas del día
            hourly_analysis = self._analyze_hourly_traffic(origin, destination)
            
            # Predicción de tráfico
            traffic_prediction = self._predict_traffic_conditions(
                departure_time, 
                route_data['traffic_conditions']
            )
            
            # Recomendaciones
            recommendations = self._generate_traffic_recommendations(
                route_data, 
                hourly_analysis, 
                traffic_prediction
            )
            
            result = {
                'success': True,
                'current_conditions': route_data['traffic_conditions'],
                'hourly_analysis': hourly_analysis,
                'prediction': traffic_prediction,
                'recommendations': recommendations,
                'optimal_departure_times': self._find_optimal_times(hourly_analysis),
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"Error en análisis de tráfico: {e}")
            return {'success': False, 'error': 'Error en análisis de tráfico'}
    
    def _analyze_hourly_traffic(self, origin: str, destination: str) -> Dict:
        """Analiza patrones de tráfico por horas"""
        # Simular análisis histórico de tráfico
        hours_data = {}
        
        for hour in range(24):
            if 7 <= hour <= 9 or 17 <= hour <= 19:  # Horas pico
                condition = 'heavy'
                delay_factor = 1.5 + (hour % 2) * 0.3
            elif 10 <= hour <= 16:  # Horas normales
                condition = 'moderate'
                delay_factor = 1.1 + (hour % 3) * 0.1
            else:  # Horas valle
                condition = 'light'
                delay_factor = 0.8 + (hour % 4) * 0.05
            
            hours_data[f"{hour:02d}:00"] = {
                'condition': condition,
                'delay_factor': round(delay_factor, 2),
                'recommended': condition == 'light'
            }
        
        return hours_data
    
    def _predict_traffic_conditions(self, departure_time: datetime, 
                                  current_conditions: Dict) -> Dict:
        """Predice condiciones de tráfico"""
        hour = departure_time.hour
        
        # Lógica predictiva simple
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            predicted_condition = 'heavy'
            confidence = 0.9
        elif 10 <= hour <= 16:
            predicted_condition = 'moderate'
            confidence = 0.7
        else:
            predicted_condition = 'light'
            confidence = 0.8
        
        return {
            'condition': predicted_condition,
            'confidence': confidence,
            'departure_time': departure_time.isoformat(),
            'factors': {
                'time_of_day': 'peak' if 7 <= hour <= 9 or 17 <= hour <= 19 else 'normal',
                'day_of_week': departure_time.strftime('%A'),
                'weather_impact': 'low'  # TODO: integrar datos meteorológicos
            }
        }
    
    def _generate_traffic_recommendations(self, route_data: Dict, 
                                        hourly_analysis: Dict, 
                                        prediction: Dict) -> Dict:
        """Genera recomendaciones basadas en el análisis"""
        recommendations = {
            'departure_adjustment': None,
            'alternative_routes': [],
            'cost_optimization': [],
            'general_tips': []
        }
        
        # Recomendación de horario
        if prediction['condition'] == 'heavy':
            recommendations['departure_adjustment'] = {
                'suggestion': 'Considerar salir 30-60 minutos antes o después',
                'reason': 'Evitar hora pico reducirá el costo hasta 30%'
            }
        
        # Consejos generales
        recommendations['general_tips'] = [
            'Verificar tráfico en tiempo real antes de salir',
            'Considerar rutas alternativas si están disponibles',
            'En hora pico, el costo puede aumentar hasta 50%'
        ]
        
        if route_data.get('alternative_routes', 0) > 0:
            recommendations['alternative_routes'].append({
                'available': route_data['alternative_routes'],
                'suggestion': 'Evaluar rutas alternativas para optimizar tiempo y costo'
            })
        
        return recommendations
    
    def _find_optimal_times(self, hourly_analysis: Dict) -> list:
        """Encuentra las mejores horas para viajar"""
        optimal_times = []
        
        for time, data in hourly_analysis.items():
            if data['recommended'] and data['delay_factor'] < 1.0:
                optimal_times.append({
                    'time': time,
                    'condition': data['condition'],
                    'savings_percentage': round((1 - data['delay_factor']) * 100, 1)
                })
        
        return sorted(optimal_times, key=lambda x: x['savings_percentage'], reverse=True)[:5]

# Función de utilidad para integración completa
def get_complete_delivery_analysis(origin: str, destination: str, 
                                 vehicle_type: str, departure_time: Optional[datetime] = None) -> Dict:
    """Análisis completo integrando todas las APIs"""
    try:
        # Servicios
        maps_service = GoogleMapsService()
        fuel_service = ColombiaFuelService()
        traffic_service = TrafficAnalysisService()
        
        # 1. Información de ruta
        route_info = maps_service.get_detailed_route_info(origin, destination)
        
        if not route_info['success']:
            return route_info
        
        # 2. Precios de combustible
        # Detectar ciudad desde la dirección de origen
        city = 'bogota'  # Default, TODO: extraer de la dirección
        fuel_data = fuel_service.get_current_fuel_prices(city)
        
        # 3. Análisis de tráfico
        traffic_analysis = traffic_service.get_traffic_analysis(origin, destination, departure_time)
        
        # 4. Resultado integrado
        result = {
            'success': True,
            'route': route_info,
            'fuel_prices': fuel_data,
            'traffic_analysis': traffic_analysis,
            'integration_timestamp': datetime.now().isoformat(),
            'data_freshness': {
                'route_data': 'real_time',
                'fuel_prices': 'hourly_updated', 
                'traffic_analysis': 'real_time'
            }
        }
        
        return result
        
    except Exception as e:
        print(f"Error en análisis completo: {e}")
        return {'success': False, 'error': 'Error en análisis completo'}