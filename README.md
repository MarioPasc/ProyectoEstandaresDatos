# ProyectoEstandaresDatos
Repositorio Github para el proyecto final de la asignatura "Estándares de Datos"

## 🚀 Instalación y Configuración

### 1️⃣ Clonar el repositorio

```bash
git clone https://github.com/MarioPasc/ProyectoEstandaresDatos.git
cd ProyectoEstandaresDatos
```

### 2️⃣ Cambiar a la rama de desarrollo

> [!IMPORTANT]
> **DEBES** trabajar en la rama `descargarDatosAutomaticamente` para tener acceso a las últimas funcionalidades de descarga de datos.

```bash
git checkout descargarDatosAutomaticamente
```

### 3️⃣ Crear entorno Conda

> [!WARNING]
> Se requiere **Python 3.9** específicamente. No uses otras versiones.

```bash
conda create -n estandares python=3.9 -y
conda activate estandares
```

### 4️⃣ Instalar el paquete en modo desarrollo

```bash
pip install -e .
```

### 5️⃣ Configurar rutas personales

> [!CAUTION]
> **CRÍTICO**: Debes personalizar las rutas de salida antes de ejecutar descargas.

```bash
# Copiar tu archivo de configuración (reemplaza 'mario' por tu nombre)
cp config/config_files/mario_data_config.yaml config/data_config.yaml

# Editar el archivo y cambiar TODAS las rutas que contienen /home/mpascual
# por tu ruta personal (ver config/README.md para detalles)
nano config/data_config.yaml  # o usa tu editor preferido
```

**Rutas que debes cambiar** (6 en total):
- ✏️ `gdc.manifest_output`
- ✏️ `gdc.file_metadata_output`
- ✏️ `gdc.genes_output`
- ✏️ `gdc.rnaseq.output_dir`
- ✏️ `gdc.rnaseq.gene_table_output`
- ✏️ `hgnc.output_path`
- ✏️ `uniprot.mapping_output`
- ✏️ `uniprot.metadata_output`

📖 **Consulta** `config/README.md` para instrucciones detalladas.

## 📥 Descargar Datos

Una vez configurado tu archivo `config/data_config.yaml`:

```bash
# Descargar TODOS los datos (GDC + HGNC + UniProt)
datastandards-download --config config/data_config.yaml --source all

# O descargar fuentes individuales:
datastandards-download --config config/data_config.yaml --source gdc
datastandards-download --config config/data_config.yaml --source hgnc
datastandards-download --config config/data_config.yaml --source uniprot
```

> [!NOTE]
> - La descarga completa puede tardar varios minutos
> - UniProt requiere que GDC y HGNC se hayan descargado primero
> - Los directorios de salida se crean automáticamente

## 📊 Fuentes de Datos

- **GDC (Genomic Data Commons)**: Datos RNA-seq del proyecto TCGA-LGG
- **HGNC**: Nomenclatura completa de genes humanos
- **UniProt**: Anotación de proteínas asociadas a los genes del proyecto

## 🔧 Verificación

Después de la descarga, el sistema muestra automáticamente:
- ✅ Estadísticas de archivos descargados
- ✅ Número de registros y columnas
- ✅ Validaciones de integridad

## 📖 Lectura

Por favor! Leed con detenimiento [este fichero](docs/reports/T1_README_Datos.md), describe todo lo que creo que deberíamos de saber de los datos antes de empezar a trabajar con ellos 

## ❓ Problemas Comunes

**Error: "No such file or directory"**
→ Verifica que las rutas en `data_config.yaml` existan y tengas permisos de escritura

**Error: "Archivo requerido no encontrado"** (al descargar UniProt)
→ Descarga primero GDC y HGNC: `--source gdc` y `--source hgnc`

**Error: "Python version mismatch"**
→ Asegúrate de usar Python 3.9: `python --version`
