import os
from typing import Dict, Any, List
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white, red, green, orange, grey
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from schemas import TipoReporte, ParametrosReporte
import logging
import json

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.logo_path = "assets/logo_sena.png"
        self.company_name = "SERVICIO NACIONAL DE APRENDIZAJE - SENA"
        self.institutional_colors = {
            "primary": HexColor('#00af00'),    # Verde SENA
            "secondary": HexColor('#A23B72'),  # Morado
            "accent": HexColor('#F18F01'),     # Naranja
            "success": HexColor('#28a745'),
            "warning": HexColor('#ffc107'),
            "danger": HexColor('#dc3545')
        }
        
    def _setup_custom_styles(self):
        """Configura estilos personalizados mejorados para reportes estratégicos"""
        
        # Estilo para títulos principales con branding SENA
        self.styles.add(ParagraphStyle(
            name='SENATitle',
            parent=self.styles['Heading1'],
            fontSize=26,
            spaceAfter=30,
            textColor=HexColor('#00af00'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para subtítulos de secciones
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            spaceAfter=20,
            spaceBefore=25,
            textColor=HexColor('#A23B72'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para subsecciones
        self.styles.add(ParagraphStyle(
            name='SubsectionTitle',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=15,
            spaceBefore=15,
            textColor=HexColor('#F18F01'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para texto de resumen ejecutivo
        self.styles.add(ParagraphStyle(
            name='ExecutiveSummary',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=15,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=16
        ))
        
        # Estilo para conclusiones
        self.styles.add(ParagraphStyle(
            name='Conclusion',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=15,
            leftIndent=20
        ))
        
        # Estilo para recomendaciones
        self.styles.add(ParagraphStyle(
            name='Recommendation',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=14,
            leftIndent=15,
            bulletIndent=10
        ))

    def _draw_header_footer(self, canvas, doc):
        """Dibuja encabezado y pie de página institucional mejorado"""
        canvas.saveState()
        
        page_width = doc.pagesize[0]
        page_height = doc.pagesize[1]
        margin = 0.5 * inch
        
        # ENCABEZADO INSTITUCIONAL
        logo_x = margin + 0.5 * inch
        logo_y = page_height - margin - 0.5 * inch
        logo_radius = 0.4 * inch
        
        # Dibujar logo (placeholder o real)
        if os.path.exists(self.logo_path):
            try:
                logo = Image(self.logo_path, width=logo_radius*2, height=logo_radius*2)
                logo.drawOn(canvas, logo_x - logo_radius, logo_y - logo_radius)
            except:
                self._draw_sena_logo_placeholder(canvas, logo_x, logo_y, logo_radius)
        else:
            self._draw_sena_logo_placeholder(canvas, logo_x, logo_y, logo_radius)
        
        # Línea decorativa institucional
        canvas.setStrokeColor(self.institutional_colors["primary"])
        canvas.setLineWidth(3)
        canvas.line(margin, page_height - margin - 1*inch, page_width - margin, page_height - margin - 1*inch)
        
        # PIE DE PÁGINA INSTITUCIONAL
        footer_y = margin + 0.3*inch
        
        # Nombre institucional completo
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(self.institutional_colors["primary"])
        canvas.drawCentredString(page_width/2, footer_y + 0.2*inch, self.company_name)
        
        # Información adicional
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(black)
        canvas.drawCentredString(page_width/2, footer_y, "Sistema de Reportes Estratégicos")
        
        # Número de página con formato
        page_num = canvas.getPageNumber()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(page_width - margin, footer_y, f"Página {page_num}")
        
        # Fecha de generación
        fecha_generacion = datetime.now().strftime("%d/%m/%Y")
        canvas.drawString(margin, footer_y, f"Generado: {fecha_generacion}")
        
        canvas.restoreState()
    
    def _draw_sena_logo_placeholder(self, canvas, x, y, radius):
        """Dibuja placeholder del logo SENA con colores institucionales"""
        canvas.setStrokeColor(self.institutional_colors["primary"])
        canvas.setFillColor(self.institutional_colors["primary"])
        canvas.setLineWidth(3)
        
        # Círculo exterior
        canvas.circle(x, y, radius, stroke=1, fill=0)
        
        # Círculo interior más pequeño
        canvas.circle(x, y, radius*0.6, stroke=0, fill=1)
        
        # Texto SENA
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(white)
        canvas.drawCentredString(x, y-3, "SENA")

    def generar_pdf(
        self,
        tipo: TipoReporte,
        datos: Dict[str, Any],
        parametros: ParametrosReporte,
        reporte_id: int
    ) -> str:
        """Genera PDF del reporte usando ReportLab con plantilla personalizada"""
        
        # Crear directorio si no existe
        output_dir = "uploads/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        # Crear logo placeholder si no existe
        if not os.path.exists(self.logo_path):
            self._create_placeholder_logo()
        
        # Nombre del archivo
        output_path = os.path.join(output_dir, f"reporte_{reporte_id}_{tipo.value}.pdf")
        
        # Crear documento con la plantilla personalizada
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1.5*inch,
            bottomMargin=1*inch
        )
        
        # Configurar la función que dibujará header y footer en cada página
        doc.build(
            self._generar_contenido(tipo, datos, parametros, reporte_id),
            onFirstPage=self._draw_header_footer,
            onLaterPages=self._draw_header_footer
        )
        
        return output_path
    
    def _create_placeholder_logo(self):
        """Crea un logo placeholder temporal"""
        from PIL import Image as PILImage, ImageDraw
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(self.logo_path), exist_ok=True)
        
        # Crear imagen circular simple como placeholder
        size = (200, 200)
        img = PILImage.new('RGBA', size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Dibujar círculo
        draw.ellipse([10, 10, 190, 190], outline=(46, 134, 171, 255), width=5)
        
        # Guardar
        img.save(self.logo_path, 'PNG')
    
    def _generar_contenido(
        self,
        tipo: TipoReporte,
        datos: Dict[str, Any],
        parametros: ParametrosReporte,
        reporte_id: int
    ) -> List:
        """Genera contenido mejorado según el tipo de reporte"""
        
        if tipo == TipoReporte.CONSOLIDADO:
            return self._generar_reporte_consolidado_completo(datos, parametros, reporte_id)
        elif tipo == TipoReporte.INDICADORES:
            # Reporte de indicadores incluye: oferta, DOFA, escenarios
            return self._generar_reporte_indicadores_completo(datos, parametros, reporte_id)
        elif tipo == TipoReporte.PROSPECTIVA:
            # Prospectiva anual incluye: escenarios, DOFA
            return self._generar_reporte_prospectiva_completo(datos, parametros, reporte_id)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            # Análisis y oferta: solo oferta
            return self._generar_reporte_oferta_mejorado(datos, parametros, reporte_id)
        
        return []

    def _filtrar_proyecciones_relevantes(self, proyecciones: List[Dict], max_años: int = 5) -> List[Dict]:
        """
        Filtra proyecciones para mostrar solo las más relevantes
        - Próximos N años
        - Indicadores principales (demanda, población, empleo)
        """
        año_actual = datetime.now().year
        
        proyecciones_filtradas = []
        
        for p in proyecciones:
            año = p.get('año', 0)
            
            # Solo proyecciones futuras dentro del rango
            if año < año_actual or año > año_actual + max_años:
                continue
            
            # Simplificar estructura: extraer solo indicadores clave
            p_simplificada = {
                'año': año,
                'sector': p.get('sector', 'General')
            }
            
            # Buscar indicadores prioritarios
            indicadores_prioritarios = [
                'demanda', 'poblacion', 'estudiantes', 'empleo', 
                'matricula', 'oferta', 'graduados', 'egresados'
            ]
            
            # Si tiene valor_proyectado directo
            if 'valor_proyectado' in p:
                p_simplificada['valor'] = p['valor_proyectado']
                p_simplificada['indicador'] = p.get('tipo_indicador', 'Proyección')
            else:
                # Buscar en todos los campos
                for key, val in p.items():
                    if isinstance(val, (int, float)):
                        key_lower = str(key).lower()
                        for ind_prior in indicadores_prioritarios:
                            if ind_prior in key_lower:
                                p_simplificada['valor'] = val
                                p_simplificada['indicador'] = key
                                break
                        if 'valor' in p_simplificada:
                            break
            
            if 'valor' in p_simplificada:
                proyecciones_filtradas.append(p_simplificada)
        
        return proyecciones_filtradas
    def _crear_grafica_escenarios(self, escenarios_data: List[Dict]) -> Drawing:
        """
        Versión mejorada con mejor manejo de datos y validación
        Crea gráfica de líneas con proyecciones de múltiples escenarios
        """
        try:
            if not escenarios_data:
                logger.warning("No hay datos de escenarios para graficar")
                return None
            
            logger.info(f"📊 Creando gráfica con {len(escenarios_data)} escenarios")
            
            # Extraer y validar datos
            series_data = {}
            todos_años = set()
            año_actual = datetime.now().year
            
            for escenario in escenarios_data[:3]:  # Máximo 3 escenarios para claridad
                nombre = escenario.get('nombre', 'Escenario')
                proyecciones = escenario.get('proyecciones', [])
                
                if not proyecciones:
                    logger.warning(f"Escenario '{nombre}' no tiene proyecciones")
                    continue
                
                logger.info(f"   Procesando escenario '{nombre}' con {len(proyecciones)} proyecciones")
                
                # Inicializar serie para este escenario
                if nombre not in series_data:
                    series_data[nombre] = {}
                
                # Procesar cada proyección
                for p in proyecciones:
                    año = p.get('año')
                    
                    # Validar año
                    if not año or not isinstance(año, (int, float)):
                        continue
                    
                    año = int(año)
                    
                    # Filtrar solo próximos 5 años
                    if año < año_actual or año > año_actual + 5:
                        continue
                    
                    todos_años.add(año)
                    
                    # Extraer valor - intentar múltiples campos
                    valor = None
                    
                    # Opción 1: valor_proyectado directo
                    if 'valor_proyectado' in p and p['valor_proyectado'] is not None:
                        valor = float(p['valor_proyectado'])
                    # Opción 2: valor simplificado
                    elif 'valor' in p and p['valor'] is not None:
                        valor = float(p['valor'])
                    # Opción 3: buscar en campos numéricos
                    else:
                        for key, val in p.items():
                            if isinstance(val, (int, float)) and val > 0:
                                valor = float(val)
                                break
                    
                    if valor is not None:
                        # Si ya existe un valor para este año, promediar
                        if año in series_data[nombre]:
                            series_data[nombre][año] = (series_data[nombre][año] + valor) / 2
                        else:
                            series_data[nombre][año] = valor
                        
                        logger.debug(f"      Año {año}: {valor}")
            
            # Validar que tenemos datos para graficar
            if not series_data or not todos_años:
                logger.warning("No se encontraron datos válidos para graficar")
                return self._crear_mensaje_sin_datos()
            
            logger.info(f"✅ Datos procesados: {len(series_data)} series, años: {sorted(todos_años)}")
            
            # Preparar datos para la gráfica
            años_ordenados = sorted(list(todos_años))
            
            # Crear Drawing
            drawing = Drawing(480, 280)
            
            # Crear gráfica de líneas
            lc = HorizontalLineChart()
            lc.x = 60
            lc.y = 60
            lc.width = 380
            lc.height = 160
            
            # Configurar ejes
            lc.categoryAxis.categoryNames = [str(año) for año in años_ordenados]
            lc.categoryAxis.labels.angle = 0
            lc.categoryAxis.labels.fontSize = 9
            lc.categoryAxis.labels.dy = -5
            
            # Configurar eje Y con valores automáticos
            lc.valueAxis.valueMin = 0
            lc.valueAxis.valueStep = None  # Auto
            lc.valueAxis.labels.fontSize = 9
            
            # Preparar series de datos
            data = []
            colores_escenarios = {
                'optimista': self.institutional_colors["success"],
                'tendencial': self.institutional_colors["primary"],
                'pesimista': self.institutional_colors["danger"],
                'conservador': self.institutional_colors["secondary"]
            }
            
            nombres_series = []
            for idx, (nombre, valores_año) in enumerate(series_data.items()):
                # Crear serie con valores para cada año (None si no existe)
                serie = []
                for año in años_ordenados:
                    valor = valores_año.get(año)
                    serie.append(valor if valor is not None else None)
                
                data.append(serie)
                nombres_series.append(nombre)
                
                # Configurar estilo de línea
                tipo_escenario = nombre.lower()
                color = self.institutional_colors.get("accent", HexColor('#3B82F6'))
                
                # Buscar color según tipo
                for tipo_key, tipo_color in colores_escenarios.items():
                    if tipo_key in tipo_escenario:
                        color = tipo_color
                        break
                
                # Aplicar estilo
                lc.lines[idx].strokeColor = color
                lc.lines[idx].strokeWidth = 2.5
                lc.lines[idx].symbol = makeMarker('FilledCircle')
                lc.lines[idx].symbol.size = 5
                lc.lines[idx].symbol.strokeColor = color
                lc.lines[idx].symbol.fillColor = color
            
            lc.data = data
            
            # Agregar leyenda
            legend_y = 240
            legend_x = 60
            legend_spacing = 140
            
            for idx, nombre in enumerate(nombres_series):
                x_pos = legend_x + (idx * legend_spacing)
                
                # Determinar color
                tipo_escenario = nombre.lower()
                color = self.institutional_colors.get("primary", HexColor('#3B82F6'))
                for tipo_key, tipo_color in colores_escenarios.items():
                    if tipo_key in tipo_escenario:
                        color = tipo_color
                        break
                
                # Dibujar línea de leyenda
                drawing.add(Rect(x_pos, legend_y, 25, 3, 
                               fillColor=color, strokeColor=color))
                
                # Texto de leyenda (truncar si es muy largo)
                texto_nombre = nombre[:18] + '...' if len(nombre) > 18 else nombre
                drawing.add(String(x_pos + 30, legend_y - 2, 
                                 texto_nombre, fontSize=9, fillColor=black))
            
            # Título
            drawing.add(String(240, 260, 'Proyecciones de Escenarios', 
                             fontSize=13, fillColor=self.institutional_colors["primary"], 
                             fontName='Helvetica-Bold', textAnchor='middle'))
            
            # Subtítulo con rango de años
            año_min = min(años_ordenados)
            año_max = max(años_ordenados)
            drawing.add(String(240, 245, f'Período: {año_min} - {año_max}', 
                             fontSize=9, fillColor=grey, textAnchor='middle'))
            
            drawing.add(lc)
            
            logger.info("✅ Gráfica creada exitosamente")
            return drawing
            
        except Exception as e:
            logger.error(f"❌ Error creando gráfica de escenarios: {str(e)}", exc_info=True)
            return self._crear_mensaje_sin_datos()
        
    def _crear_mensaje_sin_datos(self) -> Drawing:
        """Crea un mensaje visual cuando no hay datos para graficar"""
        drawing = Drawing(480, 280)
        
        # Fondo suave
        drawing.add(Rect(60, 60, 380, 160, 
                        fillColor=HexColor('#F5F5F5'), 
                        strokeColor=grey, strokeWidth=1))
        
        # Mensaje
        drawing.add(String(240, 150, 'No hay datos suficientes para generar la gráfica', 
                        fontSize=12, fillColor=grey, 
                        textAnchor='middle', fontName='Helvetica-Bold'))
        
        drawing.add(String(240, 130, 'Agregue escenarios con proyecciones para visualizar', 
                        fontSize=10, fillColor=grey, textAnchor='middle'))
        
        return drawing


    def _generar_reporte_consolidado_completo(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """
        Genera reporte consolidado completo con todos los elementos requeridos
        """
        story = []
        
        # 1. PORTADA CON TÍTULO Y FECHA
        portada = datos.get("portada", {})
        story.append(Paragraph(portada.get("titulo", "Informe Estratégico Consolidado"), self.styles['SENATitle']))
        story.append(Spacer(1, 20))
        story.append(Paragraph(portada.get("subtitulo", ""), self.styles['SectionTitle']))
        story.append(Spacer(1, 30))
        
        # Información de portada
        info_portada = [
            ['Período de Análisis:', portada.get("periodo", "")],
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['ID del Reporte:', str(reporte_id)],
            ['Versión:', portada.get("version", "1.0")]
        ]
        
        tabla_portada = Table(info_portada, colWidths=[2.5*inch, 3.5*inch])
        tabla_portada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(tabla_portada)
        story.append(PageBreak())
        
        # 2. TABLA DE CONTENIDO MEJORADA
        story.append(Paragraph("Tabla de Contenido", self.styles['SectionTitle']))
        story.append(Spacer(1, 20))
        
        secciones_contenido = [
            ("1. Resumen Ejecutivo", 3),
            ("2. Análisis DOFA", 4),
            ("3. Indicadores Estratégicos", 5),
            ("4. Análisis Prospectivo", 6),
            ("   4.1. Escenarios Prospectivos", 6),
            ("   4.2. Tendencias Sectoriales", 7),
            ("   4.3. Factores Clave", 8),
            ("5. Oferta Educativa", 9),
            ("6. Documentos de Referencia", 10),
            ("7. Conclusiones y Recomendaciones", 11)
        ]
        
        contenido_style = ParagraphStyle(
            'ContenidoItem',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=18,
            leftIndent=0,
            spaceAfter=5
        )
        
        for seccion, pagina in secciones_contenido:
            indent = 0
            if seccion.startswith("   "):
                indent = 30
                seccion = seccion.strip()
            
            contenido_item_style = ParagraphStyle(
                'ContenidoItemDynamic',
                parent=contenido_style,
                leftIndent=indent
            )
            
            texto = f'<b>{seccion}</b>' + '.' * (70 - len(seccion)) + f'<i>{pagina}</i>'
            story.append(Paragraph(texto, contenido_item_style))
        
        story.append(PageBreak())
        
        # 3. RESUMEN EJECUTIVO
        story.append(Paragraph("1. Resumen Ejecutivo", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        resumen_ejecutivo = datos.get("resumen_ejecutivo", {})
        
        mensaje = resumen_ejecutivo.get("mensaje_ejecutivo", "")
        if mensaje:
            story.append(Paragraph(mensaje.strip(), self.styles['ExecutiveSummary']))
            story.append(Spacer(1, 20))
        
        # Síntesis estratégica
        sintesis = resumen_ejecutivo.get("sintesis_estrategica", {})
        if sintesis:
            story.append(Paragraph("Síntesis Estratégica", self.styles['SubsectionTitle']))
            
            for categoria, items in sintesis.items():
                if items:
                    titulo_categoria = categoria.replace("_", " ").title()
                    story.append(Paragraph(f"<b>{titulo_categoria}:</b>", self.styles['Recommendation']))
                    for item in items[:3]:
                        texto_item = item.get("texto", item) if isinstance(item, dict) else str(item)
                        story.append(Paragraph(f"• {texto_item}", self.styles['Conclusion']))
                    story.append(Spacer(1, 10))
        
        # Prioridades estratégicas
        prioridades = resumen_ejecutivo.get("prioridades_estrategicas", [])
        if prioridades:
            story.append(Paragraph("Prioridades Estratégicas", self.styles['SubsectionTitle']))
            for i, prioridad in enumerate(prioridades, 1):
                story.append(Paragraph(f"{i}. {prioridad}", self.styles['Recommendation']))
        
        story.append(PageBreak())
        
        # 4. ANÁLISIS DOFA
        story.append(Paragraph("2. Análisis DOFA", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        analisis_dofa = datos.get("analisis_dofa", {})
        self._agregar_seccion_dofa(story, analisis_dofa)
        
        story.append(PageBreak())
        
        # 5. INDICADORES ESTRATÉGICOS
        story.append(Paragraph("3. Indicadores Estratégicos", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        indicadores = datos.get("indicadores_estrategicos", {})
        self._agregar_seccion_indicadores(story, indicadores)
        
        story.append(PageBreak())
        
        # 6. ANÁLISIS PROSPECTIVO (CON GRÁFICAS MEJORADAS)
        story.append(Paragraph("4. Análisis Prospectivo", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        escenarios = datos.get("escenarios_prospectivos", {})
        self._agregar_seccion_escenarios_mejorada(story, escenarios)
        
        story.append(PageBreak())
        
        # 7. OFERTA EDUCATIVA
        story.append(Paragraph("5. Oferta Educativa", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        oferta = datos.get("oferta_educativa", {})
        self._agregar_seccion_oferta(story, oferta)
        
        story.append(PageBreak())
        
        # 8. DOCUMENTOS DE REFERENCIA
        story.append(Paragraph("6. Documentos de Referencia", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        documentos = datos.get("documentos_relevantes", {})
        self._agregar_seccion_documentos(story, documentos)
        
        story.append(PageBreak())
        
        # 9. CONCLUSIONES Y RECOMENDACIONES
        story.append(Paragraph("7. Conclusiones y Recomendaciones", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        
        conclusiones = datos.get("conclusiones", {})
        self._agregar_seccion_conclusiones(story, conclusiones)
        
        return story

    def _agregar_seccion_dofa(self, story: List, dofa: Dict[str, Any]):
        """Agrega sección de análisis DOFA al reporte"""
        categorias_dofa = [
            ("fortalezas", "Fortalezas", self.institutional_colors["success"]),
            ("oportunidades", "Oportunidades", self.institutional_colors["primary"]),
            ("debilidades", "Debilidades", self.institutional_colors["warning"]),
            ("amenazas", "Amenazas", self.institutional_colors["danger"])
        ]
        
        for categoria, titulo, color in categorias_dofa:
            items = dofa.get(categoria, [])
            if items:
                story.append(Paragraph(titulo, self.styles['SubsectionTitle']))
                
                items_data = [['#', 'Descripción']]
                for i, item in enumerate(items[:10], 1):
                    texto = item.get("texto", item) if isinstance(item, dict) else str(item)
                    items_data.append([str(i), texto])
                
                tabla_items = Table(items_data, colWidths=[0.5*inch, 5*inch])
                tabla_items.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), color),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
                ]))
                
                story.append(tabla_items)
                story.append(Spacer(1, 15))

    def _agregar_seccion_indicadores(self, story: List, indicadores: Dict[str, Any]):
        """Agrega sección de indicadores estratégicos"""
        resumen = indicadores.get("resumen", {})
        if resumen:
            story.append(Paragraph("Resumen de Desempeño", self.styles['SubsectionTitle']))
            
            grafico_semaforo = self._crear_grafico_semaforo_mejorado(resumen)
            if grafico_semaforo:
                story.append(grafico_semaforo)
                story.append(Spacer(1, 20))
            
            resumen_data = [
                ['Métrica', 'Valor'],
                ['Total de Indicadores', str(resumen.get('total_indicadores', 0))],
                ['Indicadores en Verde', str(resumen.get('verde', 0))],
                ['Indicadores en Amarillo', str(resumen.get('amarillo', 0))],
                ['Indicadores en Rojo', str(resumen.get('rojo', 0))],
                ['Cumplimiento General', f"{resumen.get('cumplimiento_general', 0)}%"]
            ]
            
            tabla_resumen = Table(resumen_data, colWidths=[3*inch, 2*inch])
            tabla_resumen.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tabla_resumen)
            story.append(Spacer(1, 20))
        
        # Detalle de indicadores
        lista_indicadores = indicadores.get("lista", [])
        if lista_indicadores:
            story.append(Paragraph("Detalle de Indicadores", self.styles['SubsectionTitle']))
            
            headers = ['Indicador', 'Actual', 'Meta', 'Cumplimiento', 'Estado']
            indicadores_data = [headers]
            
            for ind in lista_indicadores:
                indicadores_data.append([
                    ind.get("nombre", ""),
                    f"{ind.get('valor_actual', 0)} {ind.get('unidad', '')}",
                    f"{ind.get('meta', 0)} {ind.get('unidad', '')}",
                    f"{ind.get('cumplimiento', 0)*100:.1f}%",
                    ind.get("estado_semaforo", "").upper()
                ])
            
            tabla_indicadores = Table(indicadores_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
            
            # Aplicar estilos con colores por estado
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # Aplicar colores por estado de semáforo
            for i, ind in enumerate(lista_indicadores, 1):
                color = self._get_color_semaforo(ind.get("estado_semaforo", ""))
                table_style.append(('BACKGROUND', (4, i), (4, i), color))
                if ind.get("estado_semaforo") in ['verde', 'rojo']:
                    table_style.append(('TEXTCOLOR', (4, i), (4, i), white))
            
            tabla_indicadores.setStyle(TableStyle(table_style))
            story.append(tabla_indicadores)

    def _agregar_seccion_escenarios_mejorada(self, story: List, escenarios: Dict[str, Any]):
        """
        VERSIÓN MEJORADA con gráficas de proyecciones
        """
        prospectiva = escenarios.get("prospectiva", escenarios)
        lista_escenarios = prospectiva.get("escenarios", [])
        
        # Resumen general primero
        resumen_general = prospectiva.get("resumen_general", {})
        if resumen_general:
            story.append(Paragraph("Resumen General", self.styles['SubsectionTitle']))
            
            resumen_data = [
                ['Total de Escenarios', str(resumen_general.get('total_escenarios', 0))],
                ['Total de Proyecciones', str(resumen_general.get('total_proyecciones', 0))],
                ['Sectores Cubiertos', str(resumen_general.get('sectores_unicos', 0))],
                ['Tipos de Escenarios', ', '.join(resumen_general.get('tipos_escenarios', []))]
            ]
            
            tabla_resumen = Table(resumen_data, colWidths=[2.5*inch, 3.5*inch])
            tabla_resumen.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (0, -1), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [HexColor('#E8F5E9'), white])
            ]))
            
            story.append(tabla_resumen)
            story.append(Spacer(1, 20))
        
        # *** NUEVA SECCIÓN: GRÁFICA COMPARATIVA DE TODOS LOS ESCENARIOS ***
        if lista_escenarios and len(lista_escenarios) > 1:
            story.append(Paragraph("Comparación Visual de Escenarios", self.styles['SubsectionTitle']))
            story.append(Spacer(1, 10))
            
            # Preparar datos para gráfica
            escenarios_para_grafica = []
            for escenario in lista_escenarios:
                proyecciones = escenario.get('proyecciones', [])
                if proyecciones:
                    # Filtrar proyecciones relevantes
                    proyecciones_filtradas = self._filtrar_proyecciones_relevantes(proyecciones, max_años=5)
                    
                    escenarios_para_grafica.append({
                        'nombre': escenario.get('nombre', 'Escenario'),
                        'tipo': escenario.get('tipo', ''),
                        'proyecciones': proyecciones_filtradas
                    })
            
            # Crear y agregar gráfica
            if escenarios_para_grafica:
                grafica = self._crear_grafica_escenarios(escenarios_para_grafica)
                if grafica:
                    story.append(grafica)
                    story.append(Spacer(1, 20))
        
        # Detalle de escenarios
        if lista_escenarios:
            story.append(Paragraph("Detalle de Escenarios", self.styles['SubsectionTitle']))
            
            for escenario in lista_escenarios:
                story.append(Paragraph(f"Escenario: {escenario.get('nombre', '')}", self.styles['SubsectionTitle']))
                
                # Descripción del escenario
                descripcion = escenario.get('descripcion', '')
                if descripcion:
                    story.append(Paragraph(f"<b>Descripción:</b> {descripcion}", self.styles['Normal']))
                
                # Proyecciones del escenario
                proyecciones = escenario.get('proyecciones', [])
                if proyecciones:
                    story.append(Paragraph("Proyecciones:", self.styles['Normal']))
                    
                    # Filtrar proyecciones para mostrar solo las más relevantes
                    proyecciones_filtradas = self._filtrar_proyecciones_relevantes(proyecciones, max_años=3)
                    
                    if proyecciones_filtradas:
                        proyecciones_data = [['Año', 'Sector', 'Indicador', 'Valor']]
                        for p in proyecciones_filtradas:
                            proyecciones_data.append([
                                str(p.get('año', '')),
                                p.get('sector', ''),
                                p.get('indicador', 'Proyección'),
                                str(p.get('valor', ''))
                            ])
                        
                        tabla_proyecciones = Table(proyecciones_data, colWidths=[0.7*inch, 1.5*inch, 2*inch, 1*inch])
                        tabla_proyecciones.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["secondary"]),
                            ('TEXTCOLOR', (0, 0), (-1, 0), white),
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('GRID', (0, 0), (-1, -1), 1, black),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F5F5F5')])
                        ]))
                        
                        story.append(tabla_proyecciones)
                
                story.append(Spacer(1, 15))

    def _agregar_seccion_oferta(self, story: List, oferta: Dict[str, Any]):
        """Agrega sección de oferta educativa"""
        resumen = oferta.get("resumen", {})
        if resumen:
            story.append(Paragraph("Resumen de Oferta", self.styles['SubsectionTitle']))
            
            resumen_data = [
                ['Métrica', 'Valor'],
                ['Total Programas', str(resumen.get('total_programas', 0))],
                ['Programas Activos', str(resumen.get('programas_activos', 0))],
                ['Programas en Desarrollo', str(resumen.get('programas_desarrollo', 0))],
                ['Cobertura Regional', str(resumen.get('cobertura_regional', 0))],
                ['Sectores Cubiertos', str(resumen.get('sectores_cubiertos', 0))]
            ]
            
            tabla_resumen = Table(resumen_data, colWidths=[2.5*inch, 2.5*inch])
            tabla_resumen.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["accent"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#FFF3E0')])
            ]))
            
            story.append(tabla_resumen)
            story.append(Spacer(1, 20))
        
        # Programas destacados
        programas = oferta.get("programas", [])
        if programas:
            story.append(Paragraph("Programas Destacados", self.styles['SubsectionTitle']))
            
            programas_data = [['Programa', 'Nivel', 'Duración', 'Estado', 'Demanda']]
            for prog in programas[:10]:
                programas_data.append([
                    prog.get("nombre", ""),
                    prog.get("nivel", ""),
                    prog.get("duracion", ""),
                    prog.get("estado", ""),
                    str(prog.get("demanda", ""))
                ])
            
            tabla_programas = Table(programas_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
            tabla_programas.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tabla_programas)

    def _agregar_seccion_documentos(self, story: List, documentos: Dict[str, Any]):
        """Agrega sección de documentos de referencia"""
        if not documentos:
            story.append(Paragraph("No hay documentos de referencia disponibles.", self.styles['Normal']))
            return
        
        lista_documentos = documentos.get("lista", [])
        if lista_documentos:
            story.append(Paragraph("Documentos Relevantes", self.styles['SubsectionTitle']))
            
            for i, doc in enumerate(lista_documentos, 1):
                story.append(Paragraph(f"{i}. <b>{doc.get('titulo', '')}</b>", self.styles['Normal']))
                story.append(Paragraph(f"   <i>Tipo:</i> {doc.get('tipo', '')} | <i>Fecha:</i> {doc.get('fecha', '')}", self.styles['Normal']))
                story.append(Spacer(1, 5))

    def _agregar_seccion_conclusiones(self, story: List, conclusiones: Dict[str, Any]):
        """Agrega sección de conclusiones y recomendaciones"""
        conclusiones_lista = conclusiones.get("conclusiones", [])
        recomendaciones_lista = conclusiones.get("recomendaciones", [])
        
        if conclusiones_lista:
            story.append(Paragraph("Conclusiones Principales", self.styles['SubsectionTitle']))
            for i, conclusion in enumerate(conclusiones_lista, 1):
                story.append(Paragraph(f"{i}. {conclusion}", self.styles['Conclusion']))
        
        story.append(Spacer(1, 20))
        
        if recomendaciones_lista:
            story.append(Paragraph("Recomendaciones Estratégicas", self.styles['SubsectionTitle']))
            for i, recomendacion in enumerate(recomendaciones_lista, 1):
                story.append(Paragraph(f"• {recomendacion}", self.styles['Recommendation']))

    def _get_color_semaforo(self, estado: str) -> HexColor:
        """Retorna color según estado de semáforo"""
        colores = {
            'verde': self.institutional_colors["success"],
            'amarillo': self.institutional_colors["warning"],
            'rojo': self.institutional_colors["danger"]
        }
        return colores.get(estado.lower(), grey)

    def _crear_grafico_semaforo_mejorado(self, resumen: Dict[str, Any]) -> Drawing:
        """Crea gráfico de semáforo mejorado para indicadores"""
        try:
            total = resumen.get('total_indicadores', 1)
            verde = resumen.get('verde', 0)
            amarillo = resumen.get('amarillo', 0)
            rojo = resumen.get('rojo', 0)
            
            # Crear drawing
            drawing = Drawing(400, 200)
            
            # Título
            drawing.add(String(200, 180, "Estado de Indicadores", 
                             fontSize=14, fillColor=self.institutional_colors["primary"], 
                             textAnchor="middle"))
            
            # Gráfico de pastel
            pie = Pie()
            pie.x = 150
            pie.y = 50
            pie.width = 150
            pie.height = 150
            pie.data = [verde, amarillo, rojo]
            pie.labels = [f'Verde\n{verde}', f'Amarillo\n{amarillo}', f'Rojo\n{rojo}']
            pie.slices.strokeWidth = 1
            pie.slices.strokeColor = white
            
            # Colores
            pie.slices[0].fillColor = self.institutional_colors["success"]
            pie.slices[1].fillColor = self.institutional_colors["warning"]
            pie.slices[2].fillColor = self.institutional_colors["danger"]
            
            drawing.add(pie)
            return drawing
            
        except Exception as e:
            logger.error(f"Error creando gráfico de semáforo: {e}")
            return None

    def _generar_reporte_indicadores_completo(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de indicadores con oferta, DOFA y escenarios"""
        story = []
        
        # Portada
        story.append(Paragraph("Reporte de Indicadores Estratégicos", self.styles['SENATitle']))
        story.append(Spacer(1, 20))
        
        info_portada = [
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['ID del Reporte:', str(reporte_id)],
            ['Tipo:', 'Indicadores Estratégicos']
        ]
        
        tabla_portada = Table(info_portada, colWidths=[2.5*inch, 3.5*inch])
        tabla_portada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(tabla_portada)
        story.append(PageBreak())
        
        # Tabla de contenido
        story.append(Paragraph("Tabla de Contenido", self.styles['SectionTitle']))
        story.append(Spacer(1, 20))
        
        secciones = [
            ("1. Indicadores Estratégicos", 3),
            ("2. Oferta Educativa", 4),
            ("3. Análisis DOFA", 5),
            ("4. Escenarios Prospectivos", 6)
        ]
        
        for seccion, pagina in secciones:
            texto = f'<b>{seccion}</b>' + '.' * (70 - len(seccion)) + f'<i>{pagina}</i>'
            story.append(Paragraph(texto, self.styles['Normal']))
        
        story.append(PageBreak())
        
        # 1. Indicadores
        story.append(Paragraph("1. Indicadores Estratégicos", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        self._agregar_seccion_indicadores(story, datos.get("indicadores_estrategicos", {}))
        story.append(PageBreak())
        
        # 2. Oferta Educativa
        oferta = datos.get("oferta_educativa", {})
        if oferta:
            story.append(Paragraph("2. Oferta Educativa", self.styles['SectionTitle']))
            story.append(Spacer(1, 15))
            self._agregar_seccion_oferta(story, oferta)
            story.append(PageBreak())
        
        # 3. DOFA
        dofa = datos.get("analisis_dofa", {})
        if dofa:
            story.append(Paragraph("3. Análisis DOFA", self.styles['SectionTitle']))
            story.append(Spacer(1, 15))
            self._agregar_seccion_dofa(story, dofa)
            story.append(PageBreak())
        
        # 4. Escenarios
        escenarios = datos.get("escenarios_prospectivos", {})
        if escenarios:
            story.append(Paragraph("4. Escenarios Prospectivos", self.styles['SectionTitle']))
            story.append(Spacer(1, 15))
            drawing = self._crear_grafica_escenarios(escenarios.get("escenarios", []))
            if drawing:
                story.append(drawing)
            self._agregar_seccion_escenarios_mejorada(story, escenarios)
        
        return story

    def _generar_reporte_prospectiva_completo(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de prospectiva anual con escenarios y DOFA"""
        story = []
        
        # Portada
        story.append(Paragraph("Análisis de Prospectiva Estratégica", self.styles['SENATitle']))
        story.append(Spacer(1, 20))
        
        info_portada = [
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['ID del Reporte:', str(reporte_id)],
            ['Tipo:', 'Prospectiva Anual']
        ]
        
        tabla_portada = Table(info_portada, colWidths=[2.5*inch, 3.5*inch])
        tabla_portada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(tabla_portada)
        story.append(PageBreak())
        
        # Tabla de contenido
        story.append(Paragraph("Tabla de Contenido", self.styles['SectionTitle']))
        story.append(Spacer(1, 20))
        
        secciones = [
            ("1. Escenarios Prospectivos", 3),
            ("2. Análisis DOFA", 4)
        ]
        
        for seccion, pagina in secciones:
            texto = f'<b>{seccion}</b>' + '.' * (70 - len(seccion)) + f'<i>{pagina}</i>'
            story.append(Paragraph(texto, self.styles['Normal']))
        
        story.append(PageBreak())
        
        # 1. Escenarios
        prospectiva = datos.get("prospectiva", {})
        story.append(Paragraph("1. Escenarios Prospectivos", self.styles['SectionTitle']))
        story.append(Spacer(1, 15))
        drawing = self._crear_grafica_escenarios(prospectiva.get("escenarios", []))
        if drawing:
            story.append(drawing)
        self._agregar_seccion_escenarios_mejorada(story, prospectiva)
        story.append(PageBreak())
        
        # 2. DOFA
        dofa = datos.get("analisis_dofa", {})
        if dofa:
            story.append(Paragraph("2. Análisis DOFA", self.styles['SectionTitle']))
            story.append(Spacer(1, 15))
            self._agregar_seccion_dofa(story, dofa)
        
        return story

    def _generar_reporte_oferta_mejorado(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de oferta educativa mejorado"""
        story = []
        
        # Portada
        story.append(Paragraph("Análisis de Oferta Educativa", self.styles['SENATitle']))
        story.append(Spacer(1, 20))
        
        info_portada = [
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['ID del Reporte:', str(reporte_id)],
            ['Tipo:', 'Oferta Educativa']
        ]
        
        tabla_portada = Table(info_portada, colWidths=[2.5*inch, 3.5*inch])
        tabla_portada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(tabla_portada)
        story.append(PageBreak())
        
        # Oferta educativa
        oferta = datos.get("oferta_educativa", {})
        if oferta:
            self._agregar_seccion_oferta(story, oferta)
        
        return story

# Helper function for creating markers
def makeMarker(markerType):
    from reportlab.graphics.shapes import Circle, Rect as RectShape
    if markerType == 'FilledCircle':
        return Circle(0, 0, 4, fillColor=black, strokeColor=black)
    elif markerType == 'Rect':
        return RectShape(0, 0, 8, 8, fillColor=black, strokeColor=black)
    return None