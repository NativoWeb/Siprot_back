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
            return self._generar_reporte_indicadores_mejorado(datos, parametros, reporte_id)
        elif tipo == TipoReporte.PROSPECTIVA:
            return self._generar_reporte_prospectiva_mejorado(datos, parametros, reporte_id)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            return self._generar_reporte_oferta_mejorado(datos, parametros, reporte_id)
        
        return []

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
        
        # 2. TABLA DE CONTENIDO MEJORADA (sin usar Table)
        story.append(Paragraph("Tabla de Contenido", self.styles['SectionTitle']))
        story.append(Spacer(1, 20))
        
        # Usar párrafos en lugar de tabla
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
            # Detectar nivel de indentación
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
        
        # 3. RESUMEN EJECUTIVO (inicio claro de sección)
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
        
        # 6. ANÁLISIS PROSPECTIVO (inicio claro de sección con subsecciones)
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
                
                # Crear tabla para los items
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
        # Resumen de indicadores
        resumen = indicadores.get("resumen", {})
        if resumen:
            story.append(Paragraph("Resumen de Desempeño", self.styles['SubsectionTitle']))
            
            # Crear gráfico de semáforo si es posible
            grafico_semaforo = self._crear_grafico_semaforo_mejorado(resumen)
            if grafico_semaforo:
                story.append(grafico_semaforo)
                story.append(Spacer(1, 20))
            
            # Tabla resumen
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
        Agrega sección de análisis prospectivo MEJORADA con mejor organización
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
        
        # 4.1. Escenarios Prospectivos
        if lista_escenarios:
            story.append(Paragraph("4.1. Escenarios Prospectivos", self.styles['SubsectionTitle']))
            story.append(Spacer(1, 10))
            
            # Procesar cada escenario de forma organizada
            for i, escenario in enumerate(lista_escenarios, 1):
                # Encabezado del escenario
                tipo_info = escenario.get("tipo_clasificado", {})
                nombre_completo = f"Escenario {i}: {escenario.get('nombre', 'Sin nombre')}"
                
                story.append(Paragraph(nombre_completo, self.styles['SubsectionTitle']))
                story.append(Spacer(1, 5))
                
                # Información básica del escenario
                desc = escenario.get('descripcion', 'N/A')
                if len(desc) > 150:
                    desc = desc[:150] + '...'
                
                info_basica = [
                    ['Tipo', tipo_info.get('nombre', escenario.get('tipo', 'N/A'))],
                    ['Descripción', desc],
                    ['Proyecciones', f"{escenario.get('total_proyecciones', 0)} proyecciones en {escenario.get('sectores_cubiertos', 0)} sectores"],
                    ['Años Proyectados', ', '.join(map(str, escenario.get('años_proyectados', [])))]
                ]
                
                tabla_info = Table(info_basica, colWidths=[1.5*inch, 4.5*inch])
                tabla_info.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), HexColor('#F5F5F5')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, HexColor('#FAFAFA')])
                ]))
                
                story.append(tabla_info)
                story.append(Spacer(1, 10))
                
                # Métricas clave del escenario (si existen)
                metricas_clave = escenario.get('metricas_clave', [])
                if metricas_clave:
                    story.append(Paragraph("Métricas Clave", ParagraphStyle(
                        'MetricasTitle',
                        parent=self.styles['Normal'],
                        fontSize=10,
                        fontName='Helvetica-Bold',
                        textColor=self.institutional_colors["primary"]
                    )))
                    
                    metricas_data = [['Parámetro', 'Valor']]
                    for metrica in metricas_clave[:5]:  # Máximo 5 métricas
                        metricas_data.append([
                            metrica.get('parametro', 'N/A'),
                            str(metrica.get('valor', 'N/A'))
                        ])
                    
                    tabla_metricas = Table(metricas_data, colWidths=[2.5*inch, 2*inch])
                    tabla_metricas.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["accent"]),
                        ('TEXTCOLOR', (0, 0), (-1, 0), white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#FFF8E1')])
                    ]))
                    
                    story.append(tabla_metricas)
                    story.append(Spacer(1, 10))
                
                # Resumen por sectores (formato mejorado)
                resumen_sectores = escenario.get('resumen_sectores', {})
                if resumen_sectores:
                    story.append(Paragraph("Proyecciones por Sector", ParagraphStyle(
                        'SectorTitle',
                        parent=self.styles['Normal'],
                        fontSize=10,
                        fontName='Helvetica-Bold',
                        textColor=self.institutional_colors["primary"]
                    )))
                    
                    sectores_data = [['Sector', 'Proyecciones', 'Años', 'Crecimiento Promedio']]
                    for sector, info in resumen_sectores.items():
                        sectores_data.append([
                            sector,
                            str(info.get('total_proyecciones', 0)),
                            ', '.join(map(str, info.get('años', []))),
                            f"{info.get('crecimiento_promedio', 0)}%"
                        ])
                    
                    tabla_sectores = Table(sectores_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1*inch])
                    tabla_sectores.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["secondary"]),
                        ('TEXTCOLOR', (0, 0), (-1, 0), white),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
                    ]))
                    
                    story.append(tabla_sectores)
                
                story.append(Spacer(1, 15))
                
                # Separador entre escenarios
                if i < len(lista_escenarios):
                    story.append(Spacer(1, 10))
        
        # 4.2. Tendencias Sectoriales
        story.append(Paragraph("4.2. Tendencias Sectoriales", self.styles['SubsectionTitle']))
        story.append(Spacer(1, 10))
        
        tendencias = escenarios.get("tendencias_sectoriales", prospectiva.get("tendencias_sectoriales", []))
        if tendencias:
            tendencias_data = [['Sector', 'Crecimiento (%)', 'Demanda', 'Factores Clave']]
            for t in tendencias:
                factores = ", ".join(t.get("factores", [])[:3]) if t.get("factores") else "N/A"
                if len(factores) > 60:
                    factores = factores[:60] + "..."
                tendencias_data.append([
                    t.get("sector", ""),
                    f"{t.get('crecimiento_esperado', 0)}%",
                    t.get("demanda", ""),
                    factores
                ])
            
            tabla_tendencias = Table(tendencias_data, colWidths=[1.5*inch, 1*inch, 1*inch, 2.5*inch])
            tabla_tendencias.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["secondary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tabla_tendencias)
        else:
            story.append(Paragraph("No hay tendencias sectoriales disponibles", self.styles['ExecutiveSummary']))
        
        story.append(Spacer(1, 15))
        
        # 4.3. Factores Clave
        story.append(Paragraph("4.3. Factores Clave", self.styles['SubsectionTitle']))
        story.append(Spacer(1, 10))
        
        factores = escenarios.get("factores_clave", prospectiva.get("factores_clave", []))
        if factores:
            factores_data = [['#', 'Factor Clave']]
            for i, factor in enumerate(factores, 1):
                factores_data.append([str(i), factor])
            
            tabla_factores = Table(factores_data, colWidths=[0.5*inch, 5.5*inch])
            tabla_factores.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
            ]))
            
            story.append(tabla_factores)
        else:
            story.append(Paragraph("No hay factores clave identificados", self.styles['ExecutiveSummary']))

    def _agregar_seccion_oferta(self, story: List, oferta: Dict[str, Any]):
        """Agrega sección de oferta educativa"""
        # Resumen general
        story.append(Paragraph("Resumen General", self.styles['SubsectionTitle']))
        
        resumen_data = [
            ['Métrica', 'Valor'],
            ['Total de Programas', str(oferta.get('total_programas', 0))],
            ['Total de Cupos', str(oferta.get('total_cupos', 0))],
            ['Total de Estudiantes', str(oferta.get('total_estudiantes', 0))],
            ['Ocupación Promedio', f"{oferta.get('ocupacion_promedio', 0)}%"],
            ['Sectores Atendidos', str(oferta.get('sectores_atendidos', 0))]
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
        
        # Programas por sector
        programas_sector = oferta.get("programas_por_sector", [])
        if programas_sector:
            story.append(Paragraph("Programas por Sector", self.styles['SubsectionTitle']))
            
            sector_data = [['Sector', 'Programas', 'Cupos', 'Estudiantes', 'Ocupación']]
            for p in programas_sector:
                sector_data.append([
                    p.get("sector", ""),
                    str(p.get("programas_activos", 0)),
                    str(p.get("cupos", 0)),
                    str(p.get("estudiantes_actuales", 0)),
                    f"{p.get('ocupacion', 0)}%"
                ])
            
            tabla_sectores = Table(sector_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            tabla_sectores.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["secondary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tabla_sectores)

    def _agregar_seccion_documentos(self, story: List, documentos: Dict[str, Any]):
        """Agrega sección de documentos de referencia"""
        documentos_destacados = documentos.get("documentos_destacados", [])
        
        if documentos_destacados:
            story.append(Paragraph("Documentos Destacados", self.styles['SubsectionTitle']))
            
            docs_data = [['Título', 'Fecha', 'Relevancia']]
            for doc in documentos_destacados[:10]:
                fecha = doc.get("fecha_subida", "")
                if hasattr(fecha, 'strftime'):
                    fecha = fecha.strftime('%d/%m/%Y')
                
                titulo = doc.get("titulo", "")
                if len(titulo) > 50:
                    titulo = titulo[:50] + "..."
                
                docs_data.append([titulo, str(fecha), doc.get("relevancia", "")])
            
            tabla_docs = Table(docs_data, colWidths=[3.5*inch, 1.2*inch, 1*inch])
            tabla_docs.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.institutional_colors["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tabla_docs)

    def _agregar_seccion_conclusiones(self, story: List, conclusiones: Dict[str, Any]):
        """Agrega sección de conclusiones y recomendaciones"""
        # Conclusiones principales
        conclusiones_principales = conclusiones.get("conclusiones_principales", [])
        if conclusiones_principales:
            story.append(Paragraph("Conclusiones Principales", self.styles['SubsectionTitle']))
            
            for i, conclusion in enumerate(conclusiones_principales, 1):
                story.append(Paragraph(f"{i}. {conclusion}", self.styles['Conclusion']))
            
            story.append(Spacer(1, 20))
        
        # Recomendaciones estratégicas
        recomendaciones = conclusiones.get("recomendaciones_estrategicas", {})
        if recomendaciones:
            story.append(Paragraph("Recomendaciones Estratégicas", self.styles['SubsectionTitle']))
            
            for plazo, recs in recomendaciones.items():
                if recs:
                    titulo_plazo = plazo.replace("_", " ").title()
                    story.append(Paragraph(titulo_plazo, self.styles['SubsectionTitle']))
                    
                    for rec in recs:
                        story.append(Paragraph(f"• {rec}", self.styles['Recommendation']))
                    
                    story.append(Spacer(1, 15))

    def _generar_reporte_indicadores_mejorado(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de indicadores mejorado"""
        story = []
        
        story.extend(self._generar_header("Reporte de Indicadores Estratégicos", reporte_id))
        
        story.append(Paragraph("Resumen Ejecutivo", self.styles['SectionTitle']))
        
        resumen = datos.get('resumen', {})
        
        semaforo_chart = self._crear_grafico_semaforo_mejorado(resumen)
        if semaforo_chart:
            story.append(semaforo_chart)
            story.append(Spacer(1, 20))
        
        self._agregar_seccion_indicadores(story, datos)
        
        return story
    
    def _generar_reporte_prospectiva_mejorado(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de prospectiva mejorado"""
        story = []
        
        story.extend(self._generar_header("Análisis de Prospectiva Estratégica", reporte_id))
        
        self._agregar_seccion_escenarios_mejorada(story, datos)
        
        return story
    
    def _generar_reporte_oferta_mejorado(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de oferta educativa mejorado"""
        story = []
        
        story.extend(self._generar_header("Análisis de Oferta Educativa Estratégica", reporte_id))
        
        self._agregar_seccion_oferta(story, datos)
        
        return story
    
    def _generar_header(self, titulo: str, reporte_id: int) -> List:
        """Genera el contenido del header del reporte"""
        elements = []
        
        elements.append(Paragraph(titulo, self.styles['SENATitle']))
        elements.append(Spacer(1, 20))
        
        info_data = [
            ['ID del Reporte:', str(reporte_id)],
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['Sistema:', 'Sistema de Reportes SENA']
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 30))
        
        return elements
    
    def _crear_grafico_semaforo_mejorado(self, resumen: Dict[str, Any]) -> Drawing:
        """Crea gráfico de semáforo mejorado para indicadores"""
        try:
            verde = resumen.get('verde', 0)
            amarillo = resumen.get('amarillo', 0)
            rojo = resumen.get('rojo', 0)
            total = verde + amarillo + rojo
            
            if total == 0:
                return None
            
            drawing = Drawing(500, 250)
            
            pie = Pie()
            pie.x = 50
            pie.y = 75
            pie.width = 120
            pie.height = 120
            
            pie.data = [verde, amarillo, rojo]
            pie.labels = [f'Verde ({verde})', f'Amarillo ({amarillo})', f'Rojo ({rojo})']
            pie.slices.strokeColor = black
            pie.slices.strokeWidth = 1
            
            pie.slices[0].fillColor = self.institutional_colors["success"]
            pie.slices[1].fillColor = self.institutional_colors["warning"] 
            pie.slices[2].fillColor = self.institutional_colors["danger"]
            
            drawing.add(pie)
            
            legend_x = 220
            legend_y = 180
            
            drawing.add(Rect(legend_x, legend_y, 20, 15, fillColor=self.institutional_colors["success"]))
            drawing.add(String(legend_x + 25, legend_y + 5, f'Verde: {verde} ({verde/total*100:.1f}%)', fontSize=11))
            
            drawing.add(Rect(legend_x, legend_y - 30, 20, 15, fillColor=self.institutional_colors["warning"]))
            drawing.add(String(legend_x + 25, legend_y - 25, f'Amarillo: {amarillo} ({amarillo/total*100:.1f}%)', fontSize=11))
            
            drawing.add(Rect(legend_x, legend_y - 60, 20, 15, fillColor=self.institutional_colors["danger"]))
            drawing.add(String(legend_x + 25, legend_y - 55, f'Rojo: {rojo} ({rojo/total*100:.1f}%)', fontSize=11))
            
            drawing.add(String(50, 220, 'Distribución de Indicadores por Estado', fontSize=14, fillColor=self.institutional_colors["primary"]))
            
            return drawing
        
        except Exception as e:
            logger.error(f"Error creando gráfico de semáforo: {e}")
            return None

    
    def _crear_grafico_semaforo(self, resumen: Dict[str, Any]) -> Drawing:
        """Crea un gráfico de pastel para el semáforo de indicadores"""
        try:
            verde = resumen.get('verde', 0)
            amarillo = resumen.get('amarillo', 0)
            rojo = resumen.get('rojo', 0)
            total = verde + amarillo + rojo
            
            if total == 0:
                return None
            
            # Crear el gráfico
            drawing = Drawing(400, 200)
            
            # Gráfico de pastel
            pie = Pie()
            pie.x = 50
            pie.y = 50
            pie.width = 100
            pie.height = 100
            
            # Datos
            pie.data = [verde, amarillo, rojo]
            pie.labels = ['Verde', 'Amarillo', 'Rojo']
            pie.slices.strokeColor = black
            pie.slices.strokeWidth = 1
            
            # Colores
            pie.slices[0].fillColor = HexColor('#28a745')  # Verde
            pie.slices[1].fillColor = HexColor('#ffc107')  # Amarillo
            pie.slices[2].fillColor = HexColor('#dc3545')  # Rojo
            
            drawing.add(pie)
            
            # Leyenda
            legend_y = 150
            drawing.add(Rect(200, legend_y, 15, 15, fillColor=HexColor('#28a745')))
            drawing.add(String(220, legend_y + 5, f'Verde: {verde}', fontSize=12))
            
            drawing.add(Rect(200, legend_y - 25, 15, 15, fillColor=HexColor('#ffc107')))
            drawing.add(String(220, legend_y - 20, f'Amarillo: {amarillo}', fontSize=12))
            
            drawing.add(Rect(200, legend_y - 50, 15, 15, fillColor=HexColor('#dc3545')))
            drawing.add(String(220, legend_y - 45, f'Rojo: {rojo}', fontSize=12))
            
            return drawing
        
        except Exception as e:
            print(f"Error creando gráfico: {e}")
            return None
    
    def _get_color_semaforo(self, estado: str) -> HexColor:
        """Obtiene el color según el estado del semáforo"""
        colores = {
            'verde': HexColor('#28a745'),
            'amarillo': HexColor('#ffc107'),
            'rojo': HexColor('#dc3545')
        }

        return colores.get(estado.lower(), HexColor('#6c757d'))

    def _process_prospective_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        """Procesa datos de prospectiva para mejorar la visualización en tablas"""
        prospectiva_data = datos.get("prospectiva", {})
        
        # Asegurar que los escenarios tengan estructura consistente
        escenarios = prospectiva_data.get("escenarios", [])
        escenarios_procesados = []
        
        for escenario in escenarios:
            # Normalizar parámetros
            parametros = escenario.get("parametros", {}) 
            if isinstance(parametros, str):
                try:
                    parametros = json.loads(parametros)
                except:
                    parametros = {"raw": parametros}
            
            escenario_procesado = {
                "nombre": escenario.get("nombre", "Escenario sin nombre"),
                "tipo": escenario.get("tipo", "No especificado"),
                "descripcion": escenario.get("descripcion", "Sin descripción disponible"),
                "parametros": parametros
            }
            escenarios_procesados.append(escenario_procesado)
        
        return {
            "prospectiva": {
                "escenarios": escenarios_procesados,
                "tendencias_sectoriales": prospectiva_data.get("tendencias_sectoriales", []),
                "factores_clave": prospectiva_data.get("factores_clave", [])
            }
        }