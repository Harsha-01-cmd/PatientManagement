# Patient Records API

A small FastAPI service for maintaining patient records in a local SQLite database. BMI and its category are calculated from height and weight whenever a record is returned.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The interactive API reference is available at `http://127.0.0.1:8000/docs`. Set `PATIENT_DATABASE_PATH` to choose a different database file.

## Endpoints

- `GET /health` checks service availability.
- `POST /patients` creates a patient record.
- `GET /patients` lists records; optional `sort_by` values are `patient_id`, `age`, `height_m`, `weight_kg`, and `bmi`. `order` can be `asc` or `desc`.
- `GET /patients/{patient_id}` retrieves one record.
- `PATCH /patients/{patient_id}` updates supplied fields.
- `DELETE /patients/{patient_id}` removes a record.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

BMI categories are informational and are not a medical diagnosis.