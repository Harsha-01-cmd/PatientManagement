from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field


DATABASE_PATH = Path(os.getenv("PATIENT_DATABASE_PATH", Path(__file__).with_name("patients.db")))
Gender = Literal["female", "male", "other"]


class PatientInput(BaseModel):
    patient_id: Annotated[str, Field(min_length=1, max_length=30)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    city: Annotated[str, Field(min_length=1, max_length=100)]
    age: Annotated[int, Field(gt=0, lt=120)]
    gender: Gender
    height_m: Annotated[float, Field(gt=0.3, le=2.5)]
    weight_kg: Annotated[float, Field(gt=0, le=500)]


class PatientChanges(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    city: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    age: Annotated[int, Field(gt=0, lt=120)] | None = None
    gender: Gender | None = None
    height_m: Annotated[float, Field(gt=0.3, le=2.5)] | None = None
    weight_kg: Annotated[float, Field(gt=0, le=500)] | None = None


class PatientRecord(PatientInput):
    bmi: float
    bmi_category: str


@contextmanager
def connect_database() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connect_database() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                height_m REAL NOT NULL,
                weight_kg REAL NOT NULL
            )"""
        )


def to_record(row: sqlite3.Row) -> PatientRecord:
    patient = dict(row)
    bmi = round(patient["weight_kg"] / patient["height_m"] ** 2, 2)
    if bmi < 18.5:
        category = "underweight"
    elif bmi < 25:
        category = "healthy"
    elif bmi < 30:
        category = "overweight"
    else:
        category = "obesity"
    return PatientRecord(**patient, bmi=bmi, bmi_category=category)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Patient Records API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/patients", response_model=PatientRecord, status_code=status.HTTP_201_CREATED)
def create_patient(patient: PatientInput) -> PatientRecord:
    try:
        with connect_database() as connection:
            connection.execute(
                """INSERT INTO patients
                (patient_id, name, city, age, gender, height_m, weight_kg)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                tuple(patient.model_dump().values()),
            )
            row = connection.execute(
                "SELECT * FROM patients WHERE patient_id = ?", (patient.patient_id,)
            ).fetchone()
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="A patient with this ID already exists") from error
    return to_record(row)


@app.get("/patients", response_model=list[PatientRecord])
def list_patients(
    sort_by: Literal["patient_id", "age", "height_m", "weight_kg", "bmi"] = Query(
        default="patient_id"
    ),
    order: Literal["asc", "desc"] = Query(default="asc"),
) -> list[PatientRecord]:
    sort_expressions = {
        "patient_id": "patient_id",
        "age": "age",
        "height_m": "height_m",
        "weight_kg": "weight_kg",
        "bmi": "weight_kg / (height_m * height_m)",
    }
    direction = "DESC" if order == "desc" else "ASC"
    with connect_database() as connection:
        rows = connection.execute(
            f"SELECT * FROM patients ORDER BY {sort_expressions[sort_by]} {direction}, patient_id"
        ).fetchall()
    return [to_record(row) for row in rows]


@app.get("/patients/{patient_id}", response_model=PatientRecord)
def get_patient(patient_id: str) -> PatientRecord:
    with connect_database() as connection:
        row = connection.execute(
            "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return to_record(row)


@app.patch("/patients/{patient_id}", response_model=PatientRecord)
def update_patient(patient_id: str, changes: PatientChanges) -> PatientRecord:
    updates = changes.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")
    with connect_database() as connection:
        cursor = connection.execute(
            "SELECT patient_id FROM patients WHERE patient_id = ?", (patient_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        assignments = ", ".join(f"{field} = ?" for field in updates)
        connection.execute(
            f"UPDATE patients SET {assignments} WHERE patient_id = ?",
            (*updates.values(), patient_id),
        )
        row = connection.execute(
            "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    return to_record(row)


@app.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: str) -> Response:
    with connect_database() as connection:
        cursor = connection.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)