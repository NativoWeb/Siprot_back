import os
from typing import Dict, Any, List
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, red, green, orange
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

from schemas import TipoReporte, ParametrosReporte

class PDFService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados"""
        # Estilo para títulos principales
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER
        ))
        
        # Estilo para subtítulos
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            textColor=HexColor('#A23B72'),
            alignment=TA_LEFT
        ))
        
        # Estilo para texto normal
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            alignment=TA_JUSTIFY
        ))
        
        # Estilo para resaltados
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=HexColor('#F18F01'),
            spaceBefore=6,
            spaceAfter=6
        ))
    
    def generar_pdf(
        self,
        tipo: TipoReporte,
        datos: Dict[str, Any],
        parametros: ParametrosReporte,
        reporte_id: int
    ) -> str:
        """Genera PDF del reporte usando ReportLab"""
        
        # Crear directorio si no existe
        output_dir = "uploads/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        # Nombre del archivo
        output_path = os.path.join(output_dir, f"reporte_{reporte_id}_{tipo.value}.pdf")
        
        # Crear documento
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Contenido del documento
        story = []
        
        # Generar contenido según tipo
        if tipo == TipoReporte.INDICADORES:
            story = self._generar_reporte_indicadores(datos, parametros, reporte_id)
        elif tipo == TipoReporte.PROSPECTIVA:
            story = self._generar_reporte_prospectiva(datos, parametros, reporte_id)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            story = self._generar_reporte_oferta(datos, parametros, reporte_id)
        elif tipo == TipoReporte.CONSOLIDADO:
            story = self._generar_reporte_consolidado(datos, parametros, reporte_id)
        
        # Construir PDF
        doc.build(story)
        
        return output_path
    
    def _generar_header(self, titulo: str, reporte_id: int) -> List:
        """Genera el header del reporte"""
        elements = []
        
        # Título principal
        elements.append(Paragraph(titulo, self.styles['CustomTitle']))
        elements.append(Spacer(1, 20))
        
        # Información del reporte
        info_data = [
            ['ID del Reporte:', str(reporte_id)],
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['Sistema:', 'Sistema de Reportes SENA']
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 30))
        
        return elements
    
    def _generar_reporte_indicadores(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de indicadores"""
        story = []
        
        # Header
        story.extend(self._generar_header("Reporte de Indicadores", reporte_id))
        
        # Resumen ejecutivo
        story.append(Paragraph("Resumen Ejecutivo", self.styles['CustomSubtitle']))
        
        resumen = datos.get('resumen', {})
        
        # Crear gráfico de semáforo
        semaforo_chart = self._crear_grafico_semaforo(resumen)
        if semaforo_chart:
            story.append(semaforo_chart)
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
        
        resumen_table = Table(resumen_data, colWidths=[3*inch, 2*inch])
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
        ]))
        
        story.append(resumen_table)
        story.append(Spacer(1, 30))
        
        # Detalle de indicadores
        story.append(Paragraph("Detalle de Indicadores", self.styles['CustomSubtitle']))
        
        indicadores = datos.get('indicadores', [])
        
        if indicadores:
            # Crear tabla de indicadores
            headers = ['Indicador', 'Valor Actual', 'Meta', 'Cumplimiento', 'Estado']
            indicadores_data = [headers]
            
            for ind in indicadores:
                color_estado = self._get_color_semaforo(ind.estado_semaforo)
                indicadores_data.append([
                    ind.nombre,
                    f"{ind.valor_actual} {ind.unidad}",
                    f"{ind.meta} {ind.unidad}",
                    f"{ind.cumplimiento * 100:.1f}%",
                    ind.estado_semaforo.upper()
                ])
            
            indicadores_table = Table(indicadores_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
            
            # Aplicar estilos a la tabla
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # Aplicar colores por estado
            for i, ind in enumerate(indicadores, 1):
                color = self._get_color_semaforo(ind.estado_semaforo)
                table_style.append(('BACKGROUND', (4, i), (4, i), color))
                if ind.estado_semaforo == 'verde':
                    table_style.append(('TEXTCOLOR', (4, i), (4, i), white))
            
            indicadores_table.setStyle(TableStyle(table_style))
            story.append(indicadores_table)
        
        # Comentarios del analista
        if parametros.comentarios_analista:
            story.append(Spacer(1, 20))
            story.append(Paragraph("Comentarios del Analista", self.styles['CustomSubtitle']))
            story.append(Paragraph(parametros.comentarios_analista, self.styles['CustomNormal']))
        
        return story
    
    def _generar_reporte_prospectiva(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de prospectiva"""
        story = []
        
        # Header
        story.extend(self._generar_header("Reporte de Prospectiva", reporte_id))
        
        # Escenarios
        story.append(Paragraph("Análisis de Escenarios", self.styles['CustomSubtitle']))
        
        escenarios = datos.get('escenarios', [])
        for escenario in escenarios:
            story.append(Paragraph(f"<b>{escenario['nombre']}</b>", self.styles['Highlight']))
            story.append(Paragraph(escenario['descripcion'], self.styles['CustomNormal']))
            story.append(Paragraph(f"Probabilidad: {escenario['probabilidad']}% | Impacto: {escenario['impacto']}", self.styles['CustomNormal']))
            
            # Recomendaciones
            story.append(Paragraph("Recomendaciones:", self.styles['CustomNormal']))
            for rec in escenario['recomendaciones']:
                story.append(Paragraph(f"• {rec}", self.styles['CustomNormal']))
            story.append(Spacer(1, 15))
        
        # Tendencias sectoriales
        story.append(Paragraph("Tendencias Sectoriales", self.styles['CustomSubtitle']))
        
        tendencias = datos.get('tendencias_sectoriales', [])
        if tendencias:
            tendencias_data = [['Sector', 'Crecimiento Esperado', 'Demanda']]
            for t in tendencias:
                tendencias_data.append([
                    t['sector'],
                    f"{t['crecimiento_esperado']}%",
                    t['demanda']
                ])
            
            tendencias_table = Table(tendencias_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
            tendencias_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(tendencias_table)
        
        # Factores clave
        story.append(Spacer(1, 20))
        story.append(Paragraph("Factores Clave", self.styles['CustomSubtitle']))
        factores = datos.get('factores_clave', [])
        for factor in factores:
            story.append(Paragraph(f"• {factor}", self.styles['CustomNormal']))
        
        return story
    
    def _generar_reporte_oferta(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte de oferta educativa"""
        story = []
        
        # Header
        story.extend(self._generar_header("Análisis de Oferta Educativa", reporte_id))
        
        # Resumen general
        story.append(Paragraph("Resumen General", self.styles['CustomSubtitle']))
        
        resumen_data = [
            ['Métrica', 'Valor'],
            ['Total de Programas', str(datos.get('total_programas', 0))],
            ['Total de Cupos', str(datos.get('total_cupos', 0))],
            ['Ocupación Promedio', f"{datos.get('ocupacion_promedio', 0)}%"]
        ]
        
        resumen_table = Table(resumen_data, colWidths=[3*inch, 2*inch])
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
        ]))
        
        story.append(resumen_table)
        story.append(Spacer(1, 20))
        
        # Programas por sector
        story.append(Paragraph("Programas por Sector", self.styles['CustomSubtitle']))
        
        programas = datos.get('programas_por_sector', [])
        if programas:
            programas_data = [['Sector', 'Programas Activos', 'Cupos', 'Ocupación']]
            for p in programas:
                programas_data.append([
                    p['sector'],
                    str(p['programas_activos']),
                    str(p['cupos']),
                    f"{p['ocupacion']}%"
                ])
            
            programas_table = Table(programas_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.3*inch])
            programas_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F0F0F0')])
            ]))
            
            story.append(programas_table)
        
        # Brechas formativas
        story.append(Spacer(1, 20))
        story.append(Paragraph("Brechas Formativas Identificadas", self.styles['CustomSubtitle']))
        
        brechas = datos.get('brechas_formativas', [])
        if brechas:
            brechas_data = [['Área', 'Demanda', 'Oferta', 'Brecha']]
            for b in brechas:
                brechas_data.append([
                    b['area'],
                    str(b['demanda']),
                    str(b['oferta']),
                    str(b['brecha'])
                ])
            
            brechas_table = Table(brechas_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            brechas_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F18F01')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#FFF8E1')])
            ]))
            
            story.append(brechas_table)
        
        return story
    
    def _generar_reporte_consolidado(self, datos: Dict[str, Any], parametros, reporte_id: int) -> List:
        """Genera reporte consolidado"""
        story = []
        
        # Header
        story.extend(self._generar_header("Reporte Consolidado", reporte_id))
        
        # Resumen ejecutivo
        story.append(Paragraph("Resumen Ejecutivo", self.styles['CustomSubtitle']))
        
        resumen_ejecutivo = datos.get('resumen_ejecutivo', {})
        
        # DOFA
        dofa_sections = [
            ('Fortalezas', resumen_ejecutivo.get('fortalezas', []), HexColor('#28a745')),
            ('Oportunidades', resumen_ejecutivo.get('oportunidades', []), HexColor('#17a2b8')),
            ('Debilidades', resumen_ejecutivo.get('debilidades', []), HexColor('#ffc107')),
            ('Amenazas', resumen_ejecutivo.get('amenazas', []), HexColor('#dc3545'))
        ]
        
        for titulo, items, color in dofa_sections:
            story.append(Paragraph(titulo, self.styles['CustomSubtitle']))
            for item in items:
                story.append(Paragraph(f"• {item}", self.styles['CustomNormal']))
            story.append(Spacer(1, 15))
        
        # Separador para nueva página
        story.append(PageBreak())
        
        # Incluir secciones de otros reportes (resumidas)
        
        # Indicadores (resumen)
        indicadores_data = datos.get('indicadores', {})
        if indicadores_data:
            story.append(Paragraph("Indicadores Clave", self.styles['CustomSubtitle']))
            resumen_ind = indicadores_data.get('resumen', {})
            story.append(Paragraph(
                f"Cumplimiento general: {resumen_ind.get('cumplimiento_general', 0)}% "
                f"({resumen_ind.get('verde', 0)} verdes, {resumen_ind.get('amarillo', 0)} amarillos, "
                f"{resumen_ind.get('rojo', 0)} rojos)",
                self.styles['CustomNormal']
            ))
            story.append(Spacer(1, 15))
        
        # Prospectiva (resumen)
        prospectiva_data = datos.get('prospectiva', {})
        if prospectiva_data:
            story.append(Paragraph("Análisis Prospectivo", self.styles['CustomSubtitle']))
            escenarios = prospectiva_data.get('escenarios', [])
            if escenarios:
                for esc in escenarios[:2]:  # Solo los primeros 2 escenarios
                    story.append(Paragraph(
                        f"<b>{esc['nombre']}</b>: {esc['descripcion']} (Probabilidad: {esc['probabilidad']}%)",
                        self.styles['CustomNormal']
                    ))
            story.append(Spacer(1, 15))
        
        # Oferta educativa (resumen)
        oferta_data = datos.get('oferta_educativa', {})
        if oferta_data:
            story.append(Paragraph("Oferta Educativa", self.styles['CustomSubtitle']))
            story.append(Paragraph(
                f"Total de programas: {oferta_data.get('total_programas', 0)}, "
                f"Cupos disponibles: {oferta_data.get('total_cupos', 0)}, "
                f"Ocupación promedio: {oferta_data.get('ocupacion_promedio', 0)}%",
                self.styles['CustomNormal']
            ))
        
        return story
    
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
        