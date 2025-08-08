from typing import Dict, List, Any
from datetime import datetime, timedelta
from schemas import TipoReporte, ParametrosReporte, IndicadorResponse

class DataService:
    """Servicio para recopilar y procesar datos"""
    
    def recopilar_datos(self, tipo: TipoReporte, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Método principal para recopilar datos"""
        if tipo == TipoReporte.INDICADORES:
            return self._datos_indicadores(parametros)
        elif tipo == TipoReporte.PROSPECTIVA:
            return self._datos_prospectiva(parametros)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            return self._datos_oferta(parametros)
        elif tipo == TipoReporte.CONSOLIDADO:
            return self._datos_consolidado(parametros)
        else:
            return {"error": "Tipo de reporte no válido"}
    
    def obtener_indicadores(self) -> List[IndicadorResponse]:
        """Obtiene lista de indicadores con datos hardcodeados"""
        indicadores_data = [
            {
                "id": "empleabilidad_egresados",
                "nombre": "Empleabilidad de Egresados",
                "valor_actual": 82.5,
                "meta": 85.0,
                "unidad": "porcentaje",
                "fecha_actualizacion": datetime.now() - timedelta(days=7),
                "tendencia": "positiva",
                "descripcion": "Porcentaje de egresados empleados a los 6 meses",
                "categoria": "Impacto"
            },
            {
                "id": "pertinencia_programas",
                "nombre": "Pertinencia de Programas",
                "valor_actual": 78.3,
                "meta": 80.0,
                "unidad": "porcentaje",
                "fecha_actualizacion": datetime.now() - timedelta(days=3),
                "tendencia": "estable",
                "descripcion": "Alineación de programas con necesidades del sector",
                "categoria": "Calidad"
            },
            {
                "id": "cobertura_formacion",
                "nombre": "Cobertura de Formación",
                "valor_actual": 65.2,
                "meta": 75.0,
                "unidad": "porcentaje",
                "fecha_actualizacion": datetime.now() - timedelta(days=1),
                "tendencia": "negativa",
                "descripcion": "Cobertura de población objetivo en formación",
                "categoria": "Acceso"
            },
            {
                "id": "satisfaccion_empresas",
                "nombre": "Satisfacción de Empresas",
                "valor_actual": 88.7,
                "meta": 85.0,
                "unidad": "porcentaje",
                "fecha_actualizacion": datetime.now() - timedelta(days=5),
                "tendencia": "positiva",
                "descripcion": "Nivel de satisfacción de empresas con egresados",
                "categoria": "Impacto"
            },
            {
                "id": "innovacion_curricular",
                "nombre": "Innovación Curricular",
                "valor_actual": 45.8,
                "meta": 60.0,
                "unidad": "porcentaje",
                "fecha_actualizacion": datetime.now() - timedelta(days=10),
                "tendencia": "positiva",
                "descripcion": "Programas con componentes de innovación",
                "categoria": "Calidad"
            }
        ]
        
        indicadores = []
        for data in indicadores_data:
            # Calcular propiedades derivadas
            cumplimiento = (data["valor_actual"] / data["meta"]) if data["meta"] > 0 else 0
            
            if cumplimiento >= 0.9:
                estado_semaforo = "verde"
            elif cumplimiento >= 0.7:
                estado_semaforo = "amarillo"
            else:
                estado_semaforo = "rojo"
            
            indicador = IndicadorResponse(
                **data,
                cumplimiento=round(cumplimiento, 2),
                estado_semaforo=estado_semaforo
            )
            indicadores.append(indicador)
        
        return indicadores
    
    def _datos_indicadores(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Datos específicos para reporte de indicadores"""
        indicadores = self.obtener_indicadores()
        
        # Filtrar si se especificaron indicadores
        if parametros.indicadores_seleccionados:
            indicadores = [
                ind for ind in indicadores
                if ind.id in parametros.indicadores_seleccionados
            ]
        
        # Calcular resumen
        total = len(indicadores)
        verde = len([i for i in indicadores if i.estado_semaforo == "verde"])
        amarillo = len([i for i in indicadores if i.estado_semaforo == "amarillo"])
        rojo = len([i for i in indicadores if i.estado_semaforo == "rojo"])
        
        # Estadísticas por categoría
        categorias = {}
        for ind in indicadores:
            if ind.categoria not in categorias:
                categorias[ind.categoria] = {"total": 0, "cumplimiento_promedio": 0}
            categorias[ind.categoria]["total"] += 1
            categorias[ind.categoria]["cumplimiento_promedio"] += ind.cumplimiento
        
        for cat in categorias:
            categorias[cat]["cumplimiento_promedio"] = round(
                categorias[cat]["cumplimiento_promedio"] / categorias[cat]["total"], 2
            )
        
        return {
            "indicadores": indicadores,
            "resumen": {
                "total_indicadores": total,
                "verde": verde,
                "amarillo": amarillo,
                "rojo": rojo,
                "cumplimiento_general": round((verde / total * 100) if total > 0 else 0, 1)
            },
            "categorias": categorias,
            "periodo": {
                "inicio": parametros.fecha_inicio or datetime(2024, 1, 1),
                "fin": parametros.fecha_fin or datetime.now()
            },
            "comentarios": parametros.comentarios_analista or ""
        }
    
    def _datos_prospectiva(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Datos para prospectiva"""
        escenarios = [
            {
                "nombre": "Escenario Optimista",
                "descripcion": "Crecimiento sostenido del sector con alta demanda",
                "probabilidad": 35,
                "impacto": "Alto",
                "recomendaciones": [
                    "Ampliar oferta formativa en sectores emergentes",
                    "Fortalecer alianzas estratégicas",
                    "Invertir en infraestructura tecnológica"
                ]
            },
            {
                "nombre": "Escenario Base",
                "descripcion": "Crecimiento moderado con estabilidad",
                "probabilidad": 50,
                "impacto": "Medio",
                "recomendaciones": [
                    "Mantener calidad de programas actuales",
                    "Diversificar oferta gradualmente",
                    "Optimizar recursos existentes"
                ]
            },
            {
                "nombre": "Escenario Pesimista",
                "descripcion": "Contracción económica y reducción de demanda",
                "probabilidad": 15,
                "impacto": "Bajo",
                "recomendaciones": [
                    "Consolidar programas más demandados",
                    "Reducir costos operativos",
                    "Buscar nuevos nichos de mercado"
                ]
            }
        ]
        
        tendencias = [
            {"sector": "Tecnología", "crecimiento_esperado": 25.5, "demanda": "Alta"},
            {"sector": "Salud", "crecimiento_esperado": 18.2, "demanda": "Alta"},
            {"sector": "Manufactura", "crecimiento_esperado": 8.7, "demanda": "Media"},
            {"sector": "Servicios", "crecimiento_esperado": 12.3, "demanda": "Media"},
            {"sector": "Agropecuario", "crecimiento_esperado": 5.1, "demanda": "Baja"}
        ]
        
        return {
            "escenarios": escenarios,
            "tendencias_sectoriales": tendencias,
            "horizonte_temporal": "2025-2030",
            "factores_clave": [
                "Transformación digital",
                "Sostenibilidad ambiental",
                "Demografía laboral",
                "Políticas públicas"
            ]
        }
    
    def _datos_oferta(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Datos para oferta educativa"""
        programas_por_sector = [
            {"sector": "Tecnología", "programas_activos": 45, "cupos": 1200, "ocupacion": 92},
            {"sector": "Salud", "programas_activos": 28, "cupos": 800, "ocupacion": 88},
            {"sector": "Manufactura", "programas_activos": 35, "cupos": 950, "ocupacion": 75},
            {"sector": "Servicios", "programas_activos": 52, "cupos": 1400, "ocupacion": 83},
            {"sector": "Agropecuario", "programas_activos": 18, "cupos": 450, "ocupacion": 68}
        ]
        
        brechas_identificadas = [
            {"area": "Inteligencia Artificial", "demanda": 350, "oferta": 120, "brecha": 230},
            {"area": "Ciberseguridad", "demanda": 280, "oferta": 85, "brecha": 195},
            {"area": "Energías Renovables", "demanda": 200, "oferta": 65, "brecha": 135},
            {"area": "Biotecnología", "demanda": 150, "oferta": 45, "brecha": 105}
        ]
        
        return {
            "programas_por_sector": programas_por_sector,
            "brechas_formativas": brechas_identificadas,
            "total_programas": sum(p["programas_activos"] for p in programas_por_sector),
            "total_cupos": sum(p["cupos"] for p in programas_por_sector),
            "ocupacion_promedio": round(
                sum(p["ocupacion"] * p["cupos"] for p in programas_por_sector) / 
                sum(p["cupos"] for p in programas_por_sector), 1
            )
        }
    
    def _datos_consolidado(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Datos consolidados"""
        return {
            "indicadores": self._datos_indicadores(parametros),
            "prospectiva": self._datos_prospectiva(parametros),
            "oferta_educativa": self._datos_oferta(parametros),
            "resumen_ejecutivo": {
                "fortalezas": [
                    "Alta satisfacción de empresas con egresados",
                    "Buena empleabilidad en sectores tecnológicos",
                    "Infraestructura formativa consolidada"
                ],
                "oportunidades": [
                    "Crecimiento en sectores emergentes",
                    "Demanda de nuevas competencias digitales",
                    "Alianzas internacionales"
                ],
                "debilidades": [
                    "Baja cobertura en algunas regiones",
                    "Programas desactualizados en algunos sectores",
                    "Limitaciones en recursos tecnológicos"
                ],
                "amenazas": [
                    "Competencia de instituciones internacionales",
                    "Cambios regulatorios",
                    "Volatilidad económica"
                ]
            }
        }