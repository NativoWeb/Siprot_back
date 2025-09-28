# services/data_collectors/indicators_collector.py
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

from models import Indicador
from schemas import ParametrosReporte
from .base_collector import BaseDataCollector

logger = logging.getLogger(__name__)


class IndicatorsDataCollector(BaseDataCollector):
    """Colector de datos para indicadores estratégicos"""
    
    def collect_data(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Recolecta y procesa datos de indicadores"""
        try:
            logger.info("Iniciando recolección de datos de indicadores")
            
            # Obtener indicadores activos
            indicadores_query = self.db.query(Indicador).filter(Indicador.activo == True)
            
            # Aplicar filtros si existen
            if hasattr(parametros, 'indicadores_seleccionados') and parametros.indicadores_seleccionados:
                indicadores_query = indicadores_query.filter(Indicador.id.in_(parametros.indicadores_seleccionados))
            
            if hasattr(parametros, 'categoria') and parametros.categoria:
                indicadores_query = indicadores_query.filter(Indicador.categoria == parametros.categoria)
            
            indicadores = indicadores_query.order_by(Indicador.nombre).all()
            
            # Procesar indicadores
            indicadores_procesados = []
            resumen = {
                'total_indicadores': len(indicadores),
                'verde': 0,
                'amarillo': 0,
                'rojo': 0,
                'cumplimiento_general': 0,
                'promedio_cumplimiento': 0
            }
            
            suma_cumplimiento = 0
            
            for ind in indicadores:
                # Calcular cumplimiento
                cumplimiento = self._calcular_cumplimiento(ind.valor_actual, ind.meta)
                estado_semaforo = self._determinar_estado_semaforo(cumplimiento)
                
                # Determinar tendencia
                tendencia = self._analizar_tendencia(ind)
                
                indicador_data = {
                    'id': ind.id,
                    'nombre': ind.nombre,
                    'valor_actual': ind.valor_actual,
                    'meta': ind.meta,
                    'unidad': ind.unidad,
                    'cumplimiento': cumplimiento,
                    'estado_semaforo': estado_semaforo,
                    'tendencia': tendencia,
                    'categoria': ind.categoria,
                    'descripcion': ind.descripcion,
                    'fuente_datos': ind.fuente_datos,
                    'responsable': ind.responsable,
                    'fecha_actualizacion': ind.fecha_actualizacion,
                    'frecuencia_actualizacion': ind.frecuencia_actualizacion
                }
                
                indicadores_procesados.append(indicador_data)
                
                # Actualizar contadores del resumen
                if estado_semaforo == 'verde':
                    resumen['verde'] += 1
                elif estado_semaforo == 'amarillo':
                    resumen['amarillo'] += 1
                else:
                    resumen['rojo'] += 1
                
                suma_cumplimiento += cumplimiento
            
            # Calcular métricas de resumen
            if len(indicadores) > 0:
                resumen['promedio_cumplimiento'] = suma_cumplimiento / len(indicadores)
                resumen['cumplimiento_general'] = round((resumen['verde'] / len(indicadores)) * 100, 1)
            
            # Análisis temporal si hay datos históricos
            analisis_temporal = self._generar_analisis_temporal(indicadores)
            
            # Detectar alertas críticas
            alertas = self._detectar_alertas(indicadores_procesados)
            
            # Generar recomendaciones automáticas
            recomendaciones = self._generar_recomendaciones(indicadores_procesados, resumen)
            
            resultado = {
                'indicadores': indicadores_procesados,
                'metricas_resumen': resumen,
                'analisis_temporal': analisis_temporal,
                'alertas': alertas,
                'recomendaciones': recomendaciones,
                'contexto_dofa': self._obtener_contexto_dofa(),
                'metadata': {
                    'fecha_recoleccion': datetime.now(),
                    'total_procesados': len(indicadores),
                    'filtros_aplicados': self._extraer_filtros_aplicados(parametros),
                    'calidad_datos': self._evaluar_calidad_datos(indicadores)
                }
            }
            
            logger.info(f"Recolección completada: {len(indicadores)} indicadores procesados")
            return resultado
            
        except Exception as e:
            logger.error(f"Error en recolección de indicadores: {str(e)}")
            return {
                'error': str(e),
                'indicadores': [],
                'metricas_resumen': {},
                'metadata': {'fecha_recoleccion': datetime.now(), 'error': True}
            }
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Obtiene resumen para validación"""
        try:
            total_indicadores = self.db.query(Indicador).filter(Indicador.activo == True).count()
            
            # Indicadores por categoría
            categorias = self.db.query(
                Indicador.categoria, 
                func.count(Indicador.id)
            ).filter(Indicador.activo == True).group_by(Indicador.categoria).all()
            
            # Indicadores actualizados recientemente
            recientes = self.db.query(Indicador).filter(
                Indicador.activo == True,
                Indicador.fecha_actualizacion >= datetime.now() - timedelta(days=30)
            ).count()
            
            return {
                'total_indicadores_activos': total_indicadores,
                'categorias_disponibles': dict(categorias),
                'indicadores_actualizados_mes': recientes,
                'ultima_verificacion': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen de indicadores: {str(e)}")
            return {'total_indicadores_activos': 0, 'error': str(e)}
    
    def _calcular_cumplimiento(self, valor_actual: float, meta: float) -> float:
        """Calcula porcentaje de cumplimiento"""
        if meta == 0:
            return 0.0
        return min((valor_actual / meta), 1.0)  # Máximo 100%
    
    def _determinar_estado_semaforo(self, cumplimiento: float) -> str:
        """Determina estado del semáforo basado en cumplimiento"""
        if cumplimiento >= 0.9:  # 90% o más
            return 'verde'
        elif cumplimiento >= 0.7:  # 70% - 89%
            return 'amarillo'
        else:  # Menos de 70%
            return 'rojo'
    
    def _analizar_tendencia(self, indicador: Indicador) -> str:
        """Analiza tendencia del indicador"""
        if indicador.valores_historicos and len(indicador.valores_historicos) >= 2:
            valores = list(indicador.valores_historicos.values())
            if len(valores) >= 2:
                if valores[-1] > valores[-2]:
                    return 'creciente'
                elif valores[-1] < valores[-2]:
                    return 'decreciente'
                else:
                    return 'estable'
        
        # Fallback basado en campo tendencia si existe
        return indicador.tendencia or 'sin_datos'
    
    def _generar_analisis_temporal(self, indicadores: List[Indicador]) -> Dict[str, Any]:
        """Genera análisis temporal de indicadores"""
        try:
            # Análisis básico de evolución temporal
            tendencias_count = {'creciente': 0, 'decreciente': 0, 'estable': 0}
            
            for ind in indicadores:
                tendencia = self._analizar_tendencia(ind)
                if tendencia in tendencias_count:
                    tendencias_count[tendencia] += 1
            
            return {
                'distribucion_tendencias': tendencias_count,
                'periodo_analisis': '3 meses',  # Configurable
                'indicadores_con_historico': sum(1 for ind in indicadores if ind.valores_historicos)
            }
        except Exception as e:
            logger.error(f"Error en análisis temporal: {str(e)}")
            return {}
    
    def _detectar_alertas(self, indicadores_procesados: List[Dict]) -> List[Dict[str, Any]]:
        """Detecta alertas críticas en indicadores"""
        alertas = []
        
        # Indicadores en rojo crítico
        rojos = [ind for ind in indicadores_procesados if ind['estado_semaforo'] == 'rojo']
        if len(rojos) > 0:
            alertas.append({
                'tipo': 'indicadores_criticos',
                'nivel': 'alto',
                'mensaje': f'{len(rojos)} indicadores en estado crítico',
                'indicadores_afectados': [ind['nombre'] for ind in rojos[:5]]  # Máximo 5
            })
        
        # Indicadores sin actualización reciente
        sin_actualizar = [
            ind for ind in indicadores_procesados 
            if ind.get('fecha_actualizacion') and 
            (datetime.now() - ind['fecha_actualizacion']).days > 90
        ]
        
        if len(sin_actualizar) > 0:
            alertas.append({
                'tipo': 'datos_desactualizados',
                'nivel': 'medio',
                'mensaje': f'{len(sin_actualizar)} indicadores sin actualizar en 90+ días',
                'indicadores_afectados': [ind['nombre'] for ind in sin_actualizar[:3]]
            })
        
        return alertas
    
    def _generar_recomendaciones(self, indicadores: List[Dict], resumen: Dict) -> List[str]:
        """Genera recomendaciones automáticas"""
        recomendaciones = []
        
        # Recomendaciones basadas en cumplimiento general
        if resumen.get('cumplimiento_general', 0) < 60:
            recomendaciones.append(
                "Revisar estrategias para indicadores críticos y establecer planes de mejora urgentes"
            )
        
        # Recomendaciones por cantidad de indicadores rojos
        if resumen.get('rojo', 0) > resumen.get('total_indicadores', 0) * 0.3:
            recomendaciones.append(
                "Más del 30% de indicadores están en estado crítico. Requiere intervención inmediata"
            )
        
        # Recomendaciones de seguimiento
        if resumen.get('amarillo', 0) > 0:
            recomendaciones.append(
                f"Monitorear de cerca {resumen['amarillo']} indicadores en estado de alerta"
            )
        
        return recomendaciones
    
    def _obtener_contexto_dofa(self) -> Dict[str, Any]:
        """Obtiene contexto DOFA relacionado con indicadores"""
        # Implementación básica - puede expandirse
        return {
            'disponible': False,
            'mensaje': 'Contexto DOFA no implementado aún'
        }
    
    def _extraer_filtros_aplicados(self, parametros: ParametrosReporte) -> List[str]:
        """Extrae filtros aplicados durante la recolección"""
        filtros = []
        
        if hasattr(parametros, 'categoria') and parametros.categoria:
            filtros.append(f"Categoría: {parametros.categoria}")
        
        if hasattr(parametros, 'indicadores_seleccionados') and parametros.indicadores_seleccionados:
            filtros.append(f"Indicadores seleccionados: {len(parametros.indicadores_seleccionados)}")
        
        return filtros
    
    def _evaluar_calidad_datos(self, indicadores: List[Indicador]) -> str:
        """Evalúa calidad de los datos recolectados"""
        if not indicadores:
            return "Sin datos"
        
        # Indicadores con datos completos
        completos = sum(1 for ind in indicadores if all([
            ind.valor_actual is not None,
            ind.meta is not None,
            ind.unidad,
            ind.fecha_actualizacion
        ]))
        
        porcentaje_completos = (completos / len(indicadores)) * 100
        
        if porcentaje_completos >= 90:
            return "Excelente"
        elif porcentaje_completos >= 70:
            return "Buena"
        elif porcentaje_completos >= 50:
            return "Regular"
        else:
            return "Deficiente"