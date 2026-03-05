import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io

# Configuración de la página
st.set_page_config(page_title="Extractor de XML", layout="wide")

st.title("Extractor de Datos de Facturas (XML)")
st.markdown("""
Sube tus archivos XML de facturas (CFDI 4.0). 
El sistema extraerá la información relevante y generará un archivo Excel para descargar.
""")

def extract_cfdi_data(xml_file):
    """
    Parsea un archivo XML de CFDI y extrae los datos especificados.
    Maneja la ausencia de campos de forma segura.
    Recibe un objeto de archivo (UploadedFile).
    """
    namespaces = {
        'cfdi': 'http://www.sat.gob.mx/cfd/4',
        'pago20': 'http://www.sat.gob.mx/Pagos20',
        'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
    }

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # --- Nodos principales ---
        emisor = root.find('cfdi:Emisor', namespaces)
        receptor = root.find('cfdi:Receptor', namespaces)
        timbre = root.find('.//tfd:TimbreFiscalDigital', namespaces)
        pago = root.find('.//pago20:Pago', namespaces)
        totales_pago = root.find('.//pago20:Totales', namespaces)
        impuestos_comprobante = root.find('cfdi:Impuestos', namespaces)

        # --- Extracción de datos ---
        # Se usa .get(..., default='') para evitar errores si el atributo no existe.
        
        # Datos del Comprobante
        fecha_emision = root.get('Fecha', '')
        forma_pago = pago.get('FormaDePagoP', '') if pago is not None else root.get('FormaDePago', '')
        metodo_pago = root.get('MetodoDePago', '') # Común en CFDI de Ingreso, no en Pago
        codigo_postal = root.get('LugarExpedicion', '')
        subtotal = root.get('SubTotal', '')
        
        # El total puede venir del nodo principal o del complemento de pago
        total = totales_pago.get('MontoTotalPagos', '') if totales_pago is not None else root.get('Total', '')

        # Datos del Emisor
        rfc_emisor = emisor.get('Rfc', '') if emisor is not None else ''
        nombre_emisor = emisor.get('Nombre', '') if emisor is not None else ''
        regimen_emisor = emisor.get('RegimenFiscal', '') if emisor is not None else ''

        # Datos del Timbre Fiscal Digital (TFD)
        fecha_certificacion = timbre.get('FechaTimbrado', '') if timbre is not None else ''
        folio_fiscal = timbre.get('UUID', '') if timbre is not None else ''

        # Datos de Conceptos (se unen si hay varios)
        conceptos = [c.get('Descripcion', '') for c in root.findall('.//cfdi:Concepto', namespaces)]
        concepto_desc = " | ".join(conceptos)

        # Datos de Impuestos (simplificado para IVA)
        # Prioriza el IVA del complemento de pago si existe
        iva = totales_pago.get('TotalTrasladosImpuestoIVA16', '') if totales_pago is not None else ''
        if not iva and impuestos_comprobante is not None:
            iva = impuestos_comprobante.get('TotalImpuestosTrasladados', '')

        # Crear un diccionario con los datos extraídos
        data = {
            'Fecha Emision': fecha_emision,
            'Fecha Certificacion Sat': fecha_certificacion,
            'Rfc Emisor': rfc_emisor,
            'Nombre': nombre_emisor,
            'Régimen emisor': regimen_emisor,
            'Forma de Pago': forma_pago,
            'Metodo de Pago': metodo_pago,
            'Codigo Postal': codigo_postal,
            'Tipo de Gasto': '',  # Campo no estándar en CFDI
            'Concepto': concepto_desc,
            'Subtotal': subtotal,
            'TUA': '',  # Campo no estándar
            'Hospedaje': '',  # Campo no estándar
            'IVA': iva,
            'Tasa 0': '', 
            'IVA 8%': '', 
            'IEPS': '', 
            'ISR RET': '', 
            'IVA RET': '', 
            'Total': total,
            'Estatus': '', 
            'Estatus 2': '', 
            'Fecha Cancelacion': '', 
            'Folio Fiscal': folio_fiscal,
            'Archivo Origen': xml_file.name 
        }
        return data

    except (ET.ParseError, AttributeError) as e:
        st.error(f"Error procesando el archivo {xml_file.name}: {e}")
        return None

# Widget de carga de archivos
uploaded_files = st.file_uploader("Selecciona archivos XML", type=['xml'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    # Barra de progreso
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(uploaded_files):
        # Extraer datos
        data = extract_cfdi_data(uploaded_file)
        if data:
            all_data.append(data)
        
        # Actualizar barra de progreso
        progress_bar.progress((i + 1) / len(uploaded_files))

    if all_data:
        df = pd.DataFrame(all_data)
        
        st.success(f"Se procesaron correctamente {len(all_data)} archivos.")
        
        # Mostrar vista previa
        st.subheader("Vista Previa de Datos")
        st.dataframe(df)
        
        # Convertir DataFrame a Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Reporte CFDI')
        
        excel_data = output.getvalue()
        
        # Botón de descarga
        st.download_button(
            label="Descargar Reporte Excel",
            data=excel_data,
            file_name="reporte_cfdi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No se pudo extraer información válida de los archivos subidos.")