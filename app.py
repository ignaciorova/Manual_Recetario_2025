import streamlit as st
import sqlite3
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from datetime import datetime
import plotly.express as px

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('menu.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS technical_sheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        code TEXT,
        meal_type TEXT,
        category TEXT,
        steps TEXT,
        energy REAL,
        protein REAL,
        fat REAL,
        carbs REAL,
        cost REAL,
        portions TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sheet_id INTEGER,
        name TEXT,
        quantity REAL,
        unit TEXT,
        energy_per_unit REAL,
        protein_per_unit REAL,
        fat_per_unit REAL,
        carbs_per_unit REAL,
        cost_per_unit REAL,
        FOREIGN KEY (sheet_id) REFERENCES technical_sheets(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        meal_type TEXT,
        week INTEGER,
        start_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cycle_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id INTEGER,
        day TEXT,
        sheet_id INTEGER,
        portions INTEGER,
        FOREIGN KEY (cycle_id) REFERENCES menu_cycles(id),
        FOREIGN KEY (sheet_id) REFERENCES technical_sheets(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS seasonality (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient TEXT,
        type TEXT,
        months TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS efemerides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        date TEXT,
        sheet_id INTEGER,
        FOREIGN KEY (sheet_id) REFERENCES technical_sheets(id)
    )''')
    conn.commit()
    conn.close()

# Function to extract recipes from PDF
def extract_recipes_from_pdf(pdf_path, start_page=40, end_page=210):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file '{pdf_path}' not found. Please upload the PDF first.")

    doc = fitz.open(pdf_path)
    num_pages = len(doc)

    # Validate page range
    if num_pages == 0:
        doc.close()
        raise ValueError("The PDF document is empty.")
    if start_page < 0 or end_page >= num_pages or start_page > end_page:
        doc.close()
        raise ValueError(f"Invalid page range: {start_page}-{end_page}. The PDF has {num_pages} pages (0-based: 0 to {num_pages-1}).")

    recipes = []
    current_recipe = None
    current_section = None
    in_ingredients = False
    in_steps = False
    efemerides_recipes = []
    portions_dict = {}

    # Load portion data from pages 223-271 (adjust dynamically)
    portion_start = min(222, num_pages - 1)
    portion_end = min(270, num_pages - 1)
    for page_num in range(portion_start, portion_end + 1):
        page = doc[page_num]
        text = page.get_text("text")
        lines = text.split('\n')
        current_portion = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^\d+\s+PORCIONES$', line):
                current_portion = int(re.match(r'(\d+)\s+PORCIONES', line).group(1))
            elif current_portion and re.match(r'^[A-Za-z\s]+:\s*\d+\.\d+\s*[gml]', line):
                match = re.match(r'([A-Za-z\s]+):\s*(\d+\.\d+)\s*(g|ml)', line)
                if match:
                    name, quantity, unit = match.groups()
                    portions_dict.setdefault(name.strip(), {})[current_portion] = (float(quantity), unit)

    # Define categories and meal types
    category_mapping = {
        "BEBIDAS PARA DESAYUNO": ("Desayuno", "Bebida"),
        "BEBIDAS PARA COMPLEMENTOS": ("Complemento", "Bebida"),
        "FRUTAS PARA COMPLEMENTOS Y ALMUERZO": ("Complemento/Almuerzo", "Fruta"),
        "ENSALADAS PARA COMPLEMENTOS": ("Complemento", "Ensalada"),
        "ENSALADAS PARA ALMUERZO": ("Almuerzo", "Ensalada"),
        "ADEREZOS PARA ENSALADA": ("Complemento/Almuerzo", "Aderezo"),
        "PREPARACIONES BÁSICAS Y ACOMPANAMIENTOS": ("Complemento/Almuerzo", "Acompañamiento"),
        "DESCRIPCIÓN DE OPCIONES PARA DESAYUNO": ("Desayuno", "Plato Principal"),
        "PLATOS PRINCIPALES DE COMPLEMENTO": ("Complemento", "Plato Principal"),
        "ADICIONALES DE COMPLEMENTO": ("Complemento", "Adicional"),
        "PLATOS PRINCIPALES DE ALMUERZO": ("Almuerzo", "Plato Principal"),
        "ADICIONALES DE ALMUERZO": ("Almuerzo", "Adicional"),
        "ATOLES": ("Especial", "Atole"),
        "COMPOTAS": ("Especial", "Compota"),
        "CALDOS": ("Especial", "Caldo"),
        "CARNES PROCESADAS": ("Especial", "Carne"),
        "PURÉS HARINOSOS": ("Especial", "Puré"),
        "PURÉS VEGETALES": ("Especial", "Puré"),
        "CREMAS": ("Especial", "Crema"),
        "OPCIONES DE MENÚ PARA COMPLEMENTOS EN EFEMÉRIDES": ("Efemérides", "Complemento"),
        "OPCIONES DE MENÚ PARA ALMUERZOS EN EFEMÉRIDES": ("Efemérides", "Almuerzo"),
        "OPCIONES PARA CELEBRACIONES": ("Efemérides", "Celebración")
    }

    # Process pages for recipes (start_page to end_page)
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num]
        text = page.get_text("text")
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers
            if line.upper() in category_mapping:
                current_section = line.upper()
                continue

            # Detect recipe name
            if re.match(r'^[A-Z][A-Z\s]+$', line) and current_section:
                if current_recipe:
                    recipes.append(current_recipe)
                meal_type, category = category_mapping.get(current_section, ("Unknown", "Unknown"))
                current_recipe = {
                    "name": line,
                    "code": f"REC-{len(recipes) + 1:03d}",
                    "meal_type": meal_type,
                    "category": category,
                    "ingredients": [],
                    "steps": [],
                    "energy": 0.0,
                    "protein": 0.0,
                    "fat": 0.0,
                    "carbs": 0.0,
                    "cost": 0.0,
                    "portions": "1,5,10"  # Default portions
                }
                in_ingredients = False
                in_steps = False
                continue

            # Detect ingredients section
            if line.lower().startswith("ingredientes"):
                in_ingredients = True
                in_steps = False
                continue

            # Detect preparation steps section
            if line.lower().startswith("preparación"):
                in_ingredients = False
                in_steps = True
                continue

            # Parse ingredients
            if in_ingredients and current_recipe:
                match = re.match(r'(\d+\.?\d*)\s*(g|ml|unidad)\s*(.+)', line)
                if match:
                    quantity, unit, name = match.groups()
                    portion_data = portions_dict.get(name.strip(), {})
                    current_recipe["ingredients"].append({
                        "name": name.strip(),
                        "quantity": float(quantity),
                        "unit": unit,
                        "energy_per_unit": 0.0,  # Placeholder, update later
                        "protein_per_unit": 0.0,
                        "fat_per_unit": 0.0,
                        "carbs_per_unit": 0.0,
                        "cost_per_unit": 0.01  # Placeholder
                    })

            # Parse steps
            if in_steps and current_recipe:
                if re.match(r'^\d+\.\s*.+', line):
                    current_recipe["steps"].append(line)

    # Append the last recipe
    if current_recipe:
        recipes.append(current_recipe)

    # Extract efemerides (pages 161-179, adjust dynamically)
    efemerides_start = min(160, num_pages - 1)
    efemerides_end = min(178, num_pages - 1)
    for page_num in range(efemerides_start, efemerides_end + 1):
        page = doc[page_num]
        text = page.get_text("text")
        lines = text.split('\n')
        for line in lines:
            if re.match(r'^[A-Z][A-Z\s]+$', line) and "EFEMÉRIDES" in current_section:
                efemerides_recipes.append({"name": line, "date": "2025-05-11", "sheet_id": len(recipes) + 1})  # Placeholder date

    doc.close()
    return recipes

# Function to calculate nutrition and cost
def calculate_nutrition_and_cost(ingredients, meal_type):
    energy_targets = {"Desayuno": 210, "Complemento": 280, "Almuerzo": 600, "Especial": 300}  # kcal from page 10
    protein_targets = {"Desayuno": 9, "Complemento": 12, "Almuerzo": 27, "Especial": 13}  # g, approx 18% of energy
    fat_targets = {"Desayuno": 7, "Complemento": 9, "Almuerzo": 20, "Especial": 10}  # g, approx 30% of energy
    carbs_targets = {"Desayuno": 36, "Complemento": 48, "Almuerzo": 104, "Especial": 52}  # g, approx 52% of energy

    energy = sum(ing['quantity'] * ing['energy_per_unit'] for ing in ingredients)
    protein = sum(ing['quantity'] * ing['protein_per_unit'] for ing in ingredients)
    fat = sum(ing['quantity'] * ing['fat_per_unit'] for ing in ingredients)
    carbs = sum(ing['quantity'] * ing['carbs_per_unit'] for ing in ingredients)
    cost = sum(ing['quantity'] * ing['cost_per_unit'] for ing in ingredients)

    # Adjust to target if below (simplified scaling)
    target_energy = energy_targets.get(meal_type.split('/')[0], 300)
    if energy < target_energy:
        scale = target_energy / energy if energy > 0 else 1
        energy *= scale
        protein *= scale
        fat *= scale
        carbs *= scale
        cost *= scale

    return energy, protein, fat, carbs, cost

# Function to save recipes to database
def save_recipes_to_db(recipes):
    conn = sqlite3.connect('menu.db')
    c = conn.cursor()
    for recipe in recipes:
        energy, protein, fat, carbs, cost = calculate_nutrition_and_cost(recipe["ingredients"], recipe["meal_type"])
        c.execute('''INSERT OR REPLACE INTO technical_sheets (name, code, meal_type, category, steps, energy, protein, fat, carbs, cost, portions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (recipe["name"], recipe["code"], recipe["meal_type"], recipe["category"],
                   "\n".join(recipe["steps"]), energy, protein, fat, carbs, cost, recipe["portions"]))
        sheet_id = c.lastrowid
        for ing in recipe["ingredients"]:
            c.execute('''INSERT INTO ingredients (sheet_id, name, quantity, unit, energy_per_unit, protein_per_unit, fat_per_unit, carbs_per_unit, cost_per_unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (sheet_id, ing["name"], ing["quantity"], ing["unit"], ing["energy_per_unit"],
                       ing["protein_per_unit"], ing["fat_per_unit"], ing["carbs_per_unit"], ing["cost_per_unit"]))
    conn.commit()
    conn.close()

# Function to generate PDF report
def generate_pdf(sheet):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, f"Ficha Técnica: {sheet['name']}")
    c.drawString(100, 730, f"Código: {sheet['code']}")
    c.drawString(100, 710, f"Tipo: {sheet['meal_type']}")
    c.drawString(100, 690, f"Categoría: {sheet['category']}")
    c.drawString(100, 670, "Ingredientes:")
    y = 650
    conn = sqlite3.connect('menu.db')
    c2 = conn.cursor()
    c2.execute("SELECT name, quantity, unit FROM ingredients WHERE sheet_id = ?", (sheet['id'],))
    for ing in c2.fetchall():
        c.drawString(120, y, f"{ing[0]}: {ing[1]} {ing[2]}")
        y -= 20
    c.drawString(100, y, "Pasos de Preparación:")
    y -= 20
    for line in sheet['steps'].split('\n'):
        c.drawString(120, y, line[:80])
        y -= 20
    c.drawString(100, y, f"Nutrición: {sheet['energy']} kcal, {sheet['protein']} g proteína, {sheet['fat']} g grasa, {sheet['carbs']} g carbohidratos")
    c.drawString(100, y-20, f"Costo Estimado: ${sheet['cost']:.2f}")
    c.drawString(100, y-40, f"Porciones: {sheet['portions']}")
    c.showPage()
    c.save()
    buffer.seek(0)
    conn.close()
    return buffer

# Streamlit App
st.title("Gestión de Menús Escolares")

# Initialize database
init_db()

# Upload PDF
st.header("Cargar Manual de Menú")
uploaded_file = st.file_uploader("Sube el archivo PDF", type="pdf")
pdf_path = "menu-primaria.pdf"

if uploaded_file:
    with open(pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success("PDF cargado exitosamente")

# Extract and save recipes
if os.path.exists(pdf_path):
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    doc.close()
    st.write(f"El PDF tiene {num_pages + 1} páginas (índices 0 a {num_pages}).")
    
    col1, col2 = st.columns(2)
    with col1:
        start_page = st.number_input("Página inicial (índice 0-based)", min_value=0, max_value=num_pages - 1, value=40)
    with col2:
        end_page = st.number_input("Página final (índice 0-based)", min_value=0, max_value=num_pages - 1, value=min(210, num_pages - 1))

    if st.button("Extraer y Guardar Recetas"):
        try:
            recipes = extract_recipes_from_pdf(pdf_path, start_page, end_page)
            save_recipes_to_db(recipes)
            st.success(f"{len(recipes)} recetas extraídas y guardadas")
        except Exception as e:
            st.error(f"Error al extraer recetas: {str(e)}")
else:
    st.warning("Por favor, sube un archivo PDF antes de extraer recetas.")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Fichas Técnicas", "Ciclos de Menú", "Estacionalidad", "Reportes"])

# Tab 1: Technical Sheets
with tab1:
    st.header("Fichas Técnicas")
    action = st.selectbox("Acción", ["Ver", "Crear", "Editar", "Eliminar"])
    conn = sqlite3.connect('menu.db')
    df = pd.read_sql_query("SELECT id, name, code, meal_type, category, energy, cost, portions FROM technical_sheets", conn)

    if action == "Ver":
        group_by = st.selectbox("Agrupar por", ["Ninguno", "Categoría", "Tipo de Comida", "Ciclo"])
        if group_by == "Ciclo":
            st.write("Ciclos no implementados aún, usa Categoría o Tipo de Comida.")
        elif group_by != "Ninguno":
            group_column = "category" if group_by == "Categoría" else "meal_type"
            grouped = df.groupby(group_column)
            for name, group in grouped:
                st.subheader(name)
                st.dataframe(group[["id", "name", "code", "meal_type", "category", "energy", "cost", "portions"]])
        else:
            st.dataframe(df)

        sheet_id = st.selectbox("Ver detalles de receta", df["id"].tolist(), format_func=lambda x: df[df["id"] == x]["name"].iloc[0])
        if sheet_id:
            c = conn.cursor()
            c.execute("SELECT * FROM technical_sheets WHERE id = ?", (sheet_id,))
            sheet = c.fetchone()
            st.write(f"**Nombre**: {sheet[1]}")
            st.write(f"**Código**: {sheet[2]}")
            st.write(f"**Tipo**: {sheet[3]}")
            st.write(f"**Categoría**: {sheet[4]}")
            st.write("**Ingredientes**:")
            c.execute("SELECT name, quantity, unit FROM ingredients WHERE sheet_id = ?", (sheet_id,))
            for ing in c.fetchall():
                st.write(f"- {ing[0]}: {ing[1]} {ing[2]}")
            st.write("**Pasos**:")
            for step in sheet[5].split('\n'):
                st.write(step)
            st.write(f"**Nutrición**: {sheet[6]} kcal, {sheet[7]} g proteína, {sheet[8]} g grasa, {sheet[9]} g carbohidratos")
            st.write(f"**Costo**: ${sheet[10]:.2f}")
            st.write(f"**Porciones**: {sheet[11]}")

    elif action == "Crear":
        with st.form("create_sheet"):
            name = st.text_input("Nombre", value="Gallo Pinto")
            code = st.text_input("Código", value="REC-001")
            meal_type = st.selectbox("Tipo de Comida", ["Desayuno", "Complemento", "Almuerzo", "Especial", "Efemérides"])
            category = st.selectbox("Categoría", ["Bebida", "Ensalada", "Plato Principal", "Acompañamiento", "Atole", "Compota", "Celebración"])
            steps = st.text_area("Pasos de Preparación", value="1. Cocinar arroz.\n2. Cocinar frijoles.\n3. Mezclar con cebolla y culantro.")
            portions = st.multiselect("Porciones", ["1", "5", "10"], default=["1", "5", "10"])
            st.subheader("Ingredientes")
            ingredients = []
            num_ingredients = st.number_input("Número de Ingredientes", min_value=1, value=2)
            for i in range(int(num_ingredients)):
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                with col1:
                    ing_name = st.text_input(f"Ingrediente {i+1}", value="Arroz" if i == 0 else "Frijoles")
                with col2:
                    quantity = st.number_input(f"Cantidad {i+1}", min_value=0.0, value=100.0 if i == 0 else 50.0)
                with col3:
                    unit = st.selectbox(f"Unidad {i+1}", ["g", "ml", "unidad"], index=0)
                with col4:
                    energy = st.number_input(f"Energía (kcal/unit) {i+1}", min_value=0.0, value=3.56 if i == 0 else 1.23)
                with col5:
                    protein = st.number_input(f"Proteína (g/unit) {i+1}", min_value=0.0, value=0.07 if i == 0 else 0.07)
                with col6:
                    cost = st.number_input(f"Costo ($/unit) {i+1}", min_value=0.0, value=0.01 if i == 0 else 0.02)
                ingredients.append({
                    'name': ing_name,
                    'quantity': quantity,
                    'unit': unit,
                    'energy_per_unit': energy,
                    'protein_per_unit': protein,
                    'fat_per_unit': 0.0,
                    'carbs_per_unit': 0.0,
                    'cost_per_unit': cost
                })
            submitted = st.form_submit_button("Crear Ficha")
            if submitted:
                energy, protein, fat, carbs, cost = calculate_nutrition_and_cost(ingredients, meal_type)
                conn = sqlite3.connect('menu.db')
                c = conn.cursor()
                c.execute('''INSERT INTO technical_sheets (name, code, meal_type, category, steps, energy, protein, fat, carbs, cost, portions)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (name, code, meal_type, category, steps, energy, protein, fat, carbs, cost, ",".join(portions)))
                sheet_id = c.lastrowid
                for ing in ingredients:
                    c.execute('''INSERT INTO ingredients (sheet_id, name, quantity, unit, energy_per_unit, protein_per_unit, fat_per_unit, carbs_per_unit, cost_per_unit)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (sheet_id, ing['name'], ing['quantity'], ing['unit'], ing['energy_per_unit'],
                               ing['protein_per_unit'], ing['fat_per_unit'], ing['carbs_per_unit'], ing['cost_per_unit']))
                conn.commit()
                conn.close()
                st.success("Ficha creada exitosamente")

    elif action == "Editar":
        conn = sqlite3.connect('menu.db')
        c = conn.cursor()
        c.execute("SELECT id, name FROM technical_sheets")
        sheets = c.fetchall()
        sheet_id = st.selectbox("Seleccionar Ficha", [s[0] for s in sheets], format_func=lambda x: next(s[1] for s in sheets if s[0] == x))
        if sheet_id:
            c.execute("SELECT * FROM technical_sheets WHERE id = ?", (sheet_id,))
            sheet = c.fetchone()
            with st.form("edit_sheet"):
                name = st.text_input("Nombre", value=sheet[1])
                code = st.text_input("Código", value=sheet[2])
                meal_type = st.selectbox("Tipo de Comida", ["Desayuno", "Complemento", "Almuerzo", "Especial", "Efemérides"], index=["Desayuno", "Complemento", "Almuerzo", "Especial", "Efemérides"].index(sheet[3]))
                category = st.selectbox("Categoría", ["Bebida", "Ensalada", "Plato Principal", "Acompañamiento", "Atole", "Compota", "Celebración"], index=["Bebida", "Ensalada", "Plato Principal", "Acompañamiento", "Atole", "Compota", "Celebración"].index(sheet[4]))
                steps = st.text_area("Pasos de Preparación", value=sheet[5])
                portions = st.multiselect("Porciones", ["1", "5", "10"], default=sheet[11].split(","))
                c.execute("SELECT name, quantity, unit, energy_per_unit, protein_per_unit, fat_per_unit, carbs_per_unit, cost_per_unit FROM ingredients WHERE sheet_id = ?", (sheet_id,))
                ingredients = c.fetchall()
                st.subheader("Ingredientes")
                new_ingredients = []
                for i, ing in enumerate(ingredients):
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    with col1:
                        ing_name = st.text_input(f"Ingrediente {i+1}", value=ing[0])
                    with col2:
                        quantity = st.number_input(f"Cantidad {i+1}", min_value=0.0, value=ing[1])
                    with col3:
                        unit = st.selectbox(f"Unidad {i+1}", ["g", "ml", "unidad"], index=["g", "ml", "unidad"].index(ing[2]))
                    with col4:
                        energy = st.number_input(f"Energía (kcal/unit) {i+1}", min_value=0.0, value=ing[3])
                    with col5:
                        protein = st.number_input(f"Proteína (g/unit) {i+1}", min_value=0.0, value=ing[4])
                    with col6:
                        cost = st.number_input(f"Costo ($/unit) {i+1}", min_value=0.0, value=ing[7])
                    new_ingredients.append({
                        'name': ing_name,
                        'quantity': quantity,
                        'unit': unit,
                        'energy_per_unit': energy,
                        'protein_per_unit': protein,
                        'fat_per_unit': 0.0,
                        'carbs_per_unit': 0.0,
                        'cost_per_unit': cost
                    })
                submitted = st.form_submit_button("Actualizar Ficha")
                if submitted:
                    energy, protein, fat, carbs, cost = calculate_nutrition_and_cost(new_ingredients, meal_type)
                    c.execute('''UPDATE technical_sheets SET name=?, code=?, meal_type=?, category=?, steps=?, energy=?, protein=?, fat=?, carbs=?, cost=?, portions=?
                                WHERE id=?''',
                              (name, code, meal_type, category, steps, energy, protein, fat, carbs, cost, ",".join(portions), sheet_id))
                    c.execute("DELETE FROM ingredients WHERE sheet_id = ?", (sheet_id,))
                    for ing in new_ingredients:
                        c.execute('''INSERT INTO ingredients (sheet_id, name, quantity, unit, energy_per_unit, protein_per_unit, fat_per_unit, carbs_per_unit, cost_per_unit)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                  (sheet_id, ing['name'], ing['quantity'], ing['unit'], ing['energy_per_unit'],
                                   ing['protein_per_unit'], ing['fat_per_unit'], ing['carbs_per_unit'], ing['cost_per_unit']))
                    conn.commit()
                    st.success("Ficha actualizada")
        conn.close()

    elif action == "Eliminar":
        conn = sqlite3.connect('menu.db')
        c = conn.cursor()
        c.execute("SELECT id, name FROM technical_sheets")
        sheets = c.fetchall()
        sheet_id = st.selectbox("Seleccionar Ficha", [s[0] for s in sheets], format_func=lambda x: next(s[1] for s in sheets if s[0] == x))
        if st.button("Eliminar"):
            c.execute("DELETE FROM ingredients WHERE sheet_id = ?", (sheet_id,))
            c.execute("DELETE FROM technical_sheets WHERE id = ?", (sheet_id,))
            conn.commit()
            st.success("Ficha eliminada")
        conn.close()
    conn.close()

# Tab 2: Menu Cycles
with tab2:
    st.header("Ciclos de Menú")
    action = st.selectbox("Acción", ["Crear", "Ver"])
    
    if action == "Crear":
        with st.form("create_cycle"):
            name = st.text_input("Nombre", value="Ciclo Desayuno Semana 1")
            meal_type = st.selectbox("Tipo de Comida", ["Desayuno", "Complemento", "Almuerzo", "Especial", "Efemérides"])
            week = st.number_input("Semana", min_value=1, max_value=5, value=1)
            start_date = st.date_input("Fecha de Inicio")
            st.subheader("Días")
            conn = sqlite3.connect('menu.db')
            c = conn.cursor()
            c.execute("SELECT id, name FROM technical_sheets")
            sheets = c.fetchall()
            days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
            cycle_days = []
            for day in days:
                col1, col2 = st.columns(2)
                with col1:
                    sheet_id = st.selectbox(f"Ficha para {day}", [s[0] for s in sheets], format_func=lambda x: next(s[1] for s in sheets if s[0] == x))
                with col2:
                    portions = st.selectbox(f"Porciones para {day}", [1, 5, 10], index=2)
                cycle_days.append({'day': day, 'sheet_id': sheet_id, 'portions': portions})
            submitted = st.form_submit_button("Crear Ciclo")
            if submitted:
                c.execute('''INSERT INTO menu_cycles (name, meal_type, week, start_date)
                            VALUES (?, ?, ?, ?)''',
                          (name, meal_type, week, str(start_date)))
                cycle_id = c.lastrowid
                for day in cycle_days:
                    c.execute('''INSERT INTO cycle_days (cycle_id, day, sheet_id, portions)
                                VALUES (?, ?, ?, ?)''',
                              (cycle_id, day['day'], day['sheet_id'], day['portions']))
                conn.commit()
                conn.close()
                st.success("Ciclo creado exitosamente")

    elif action == "Ver":
        conn = sqlite3.connect('menu.db')
        df_cycles = pd.read_sql_query("SELECT id, name, meal_type, week, start_date FROM menu_cycles", conn)
        st.dataframe(df_cycles)
        if not df_cycles.empty:
            cycle_id = st.selectbox("Seleccionar Ciclo", df_cycles["id"].tolist(), format_func=lambda x: df_cycles[df_cycles["id"] == x]["name"].iloc[0])
            c.execute("SELECT day, sheet_id, portions FROM cycle_days WHERE cycle_id = ?", (cycle_id,))
            days_data = c.fetchall()
            c.execute("SELECT id, name FROM technical_sheets")
            sheets = {s[0]: s[1] for s in c.fetchall()}
            cycle_df = pd.DataFrame(days_data, columns=["Día", "Ficha ID", "Porciones"])
            cycle_df["Receta"] = cycle_df["Ficha ID"].map(sheets)
            fig = px.bar(cycle_df, x="Día", y="Porciones", text="Receta", title=f"Ciclo {df_cycles[df_cycles['id'] == cycle_id]['name'].iloc[0]}")
            st.plotly_chart(fig)
        conn.close()

# Tab 3: Seasonality
with tab3:
    st.header("Estacionalidad")
    with st.form("seasonality"):
        ingredient = st.text_input("Ingrediente", value="Mango")
        type_ = st.selectbox("Tipo", ["Fruta", "Vegetal", "Verdura Harinosa", "Aguacate"])
        months = st.multiselect("Meses Disponibles", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], default=["Mayo"])
        submitted = st.form_submit_button("Agregar")
        if submitted:
            conn = sqlite3.connect('menu.db')
            c = conn.cursor()
            c.execute('''INSERT INTO seasonality (ingredient, type, months)
                        VALUES (?, ?, ?)''',
                      (ingredient, type_, ','.join(months)))
            conn.commit()
            conn.close()
            st.success("Ingrediente agregado")
    conn = sqlite3.connect('menu.db')
    df = pd.read_sql_query("SELECT ingredient, type, months FROM seasonality", conn)
    st.dataframe(df)
    conn.close()

# Tab 4: Reports
with tab4:
    st.header("Reportes")
    conn = sqlite3.connect('menu.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM technical_sheets")
    sheets = c.fetchall()
    sheet_id = st.selectbox("Seleccionar Ficha para Reporte", [s[0] for s in sheets], format_func=lambda x: next(s[1] for s in sheets if s[0] == x))
    if st.button("Generar PDF"):
        c.execute("SELECT * FROM technical_sheets WHERE id = ?", (sheet_id,))
        sheet = c.fetchone()
        pdf_buffer = generate_pdf({
            'id': sheet[0],
            'name': sheet[1],
            'code': sheet[2],
            'meal_type': sheet[3],
            'category': sheet[4],
            'steps': sheet[5],
            'energy': sheet[6],
            'protein': sheet[7],
            'fat': sheet[8],
            'carbs': sheet[9],
            'cost': sheet[10],
            'portions': sheet[11]
        })
        st.download_button("Descargar PDF", pdf_buffer, f"{sheet[1]}.pdf", "application/pdf")
    conn.close()