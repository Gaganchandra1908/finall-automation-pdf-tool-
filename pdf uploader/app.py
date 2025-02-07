from flask import Flask, request, render_template
import pdfplumber
import mysql.connector
import os
import re

app = Flask(__name__)

# MySQL Connection Setup
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Gagan@1910",  # Replace with your MySQL password
        database="mydb"
    )
    cursor = db.cursor()
    print("✅ Database connection successful.")
except mysql.connector.Error as err:
    print(f"❌ Error: {err}")
    exit()

# Ensure 'uploads' folder exists
UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf' not in request.files:
        return "❌ No file uploaded", 400 

    file = request.files['pdf']
    if file.filename == '':
        return "❌ No selected file", 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    try:
        file.save(file_path)
        print(f"✅ File saved at: {file_path}")
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return "❌ Error saving file", 500

    try:
        process_pdf(file_path)
        return "✅ File processed and data stored in database"
    except Exception as e:
        print(f"❌ Error while processing PDF: {e}")
        return f"❌ Error while processing PDF: {e}", 500

def process_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split("\n")
                for line in lines:
                    parts = line.split()
                    if len(parts) < 5:  # Ignore short lines
                        continue

                    htno = parts[0]
                    academic_year = htno[:2]
                    branch = {
                        "05": "CSE",
                        "04": "ECE",
                        "02": "MECH",
                        "03": "EEE",
                        "42": "CSM"
                    }.get(htno[6:8], "Unknown")

                    subcode = parts[1]
                    subname_parts = []
                    for part in parts[2:]:
                        if re.search(r'\d', part):  # Stop when encountering a number
                            break
                        subname_parts.append(part)
                    subname = " ".join(subname_parts)

                    try:
                        num_parts = [p for p in parts if re.match(r'^\d+(\.\d+)?$', p) or re.match(r'^[A-Za-z\+]+$', p)]
                        internals = int(num_parts[-3])  # Last 3rd item should be internals
                        grade = num_parts[-2].strip()  # Last 2nd item should be grade
                        credits = float(num_parts[-1])  # Last item should be credits
                    except (ValueError, IndexError):
                        continue

                    year = int("20" + academic_year)
                    end_year = year + 4
                    academic_year_range = f"{year}-{end_year}"
                    academic_id = int(academic_year)

                    cursor.execute("""
                        INSERT INTO AcademicYear (academic_id, academic_year)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE academic_year = VALUES(academic_year)
                    """, (academic_id, academic_year_range))

                    for i in range(4):
                        year_entry = year + i
                        year_code = f"{academic_id}{i + 1}{branch}"
                        cursor.execute("""
                            INSERT INTO year_table (academic_id, year, branch, year_code)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE year = VALUES(year), branch = VALUES(branch), year_code = VALUES(year_code)
                        """, (academic_id, year_entry, branch, year_code))

                   
                    cursor.execute("""
                            INSERT INTO sub_table (sub_code, sub_name)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE sub_name = VALUES(sub_name)
                    """, (subcode, subname))

                    cursor.execute("SELECT sub_code FROM sub_table WHERE sub_code = %s", (subcode,))
                    if cursor.fetchone():
                        cursor.execute("""
                                INSERT INTO semsub_table (sem_id, sub_code)
                                VALUES (%s, %s)
                                ON DUPLICATE KEY UPDATE sub_code = VALUES(sub_code)
                        """, (subcode[3:5], subcode))

                    cursor.execute("""
                        INSERT INTO student_table (student_regno, academic_id, branch)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE academic_id = VALUES(academic_id), branch = VALUES(branch)
                    """, (htno, academic_id, branch))

                    cursor.execute("""
                        SELECT sub_code FROM sub_table WHERE sub_code = %s
                    """, (subcode,))
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO result_table (student_regno, sub_code, result_grade, internals,credits)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE result_grade = VALUES(result_grade), internals = VALUES(internals)
                        """, (htno, subcode, grade, internals,credits))

                    for i in range(4):
                        year_entry = year + i
                        year_code = f"{academic_id}{i + 1}{branch}"
                        if year_code[2] == subcode[3]:
                            cursor.execute("""
                                INSERT INTO year_sem (year_code, sem_id)
                                VALUES (%s, %s)
                                ON DUPLICATE KEY UPDATE sem_id = VALUES(sem_id)
                            """, (year_code, subcode[3:5]))
                    print(f"Parsed data: htno={htno}, academic_year={academic_year}, branch={branch}, subcode={subcode}, subname={subname}, internals={internals}, grade={grade}, credits={credits}")


        db.commit()
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        raise

if __name__ == '__main__':
    app.run(debug=True)
