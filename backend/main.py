from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.future import select
import httpx
import os
from dotenv import load_dotenv
import aiofiles # <<< IMPORT AIOFILES HERE

from .models import Base, Student, Assignment, AnalysisResult
from .auth import Token, authenticate_user, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, timedelta, pwd_context, fake_users_db
from .rag_service import search_sources

load_dotenv()

app = FastAPI()

DATABASE_URL = os.getenv("POSTGRES_URL").replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await init_db()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/auth/register")
async def register(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    student_id: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    existing_student_email = await db.execute(select(Student).where(Student.email == email))
    if existing_student_email.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student with this email already registered")
    
    existing_student_id = await db.execute(select(Student).where(Student.student_id == student_id))
    if existing_student_id.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student with this ID already registered")

    hashed_password = pwd_context.hash(password)
    new_student = Student(email=email, password_hash=hashed_password, full_name=full_name, student_id=student_id)
    db.add(new_student)
    await db.commit()
    await db.refresh(new_student)
    return {"msg": "Student registered successfully"}

@app.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # Query the database for the user by email
    result = await db.execute(select(Student).where(Student.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/upload")
async def upload_assignment(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    
    # <<< CORRECTED ASYNCHRONOUS FILE WRITING WITH AIOFILES >>>
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    n8n_url = os.getenv("N8N_WEBHOOK_URL")
    if not n8n_url:
        raise HTTPException(status_code=500, detail="N8N_WEBHOOK_URL not configured")

    try:
        async with httpx.AsyncClient() as client:
            # Re-open the file using aiofiles for streaming in httpx
            # This is a bit tricky: httpx expects a synchronous file-like object for `files`
            # or bytes. For full async streaming, you'd need custom content iterators for httpx
            # or send the bytes directly if the file is small enough to hold in memory.
            # For simplicity, we'll read it into memory for httpx, assuming typical assignment file sizes.
            # For very large files, a different strategy (e.g., streaming to cloud storage, then n8n processing from there)
            # would be necessary.
            file_content = await aiofiles.open(file_path, "rb")
            response = await client.post(
                n8n_url,
                files={"data": (file.filename, await file_content.read(), file.content_type)}, # Pass filename, content, and type
                data={"student_email": current_user.email, "student_id": current_user.student_id, "filename": file.filename}
            )
            file_content.close() # Close the aiofiles file handle
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger analysis in n8n: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error while contacting n8n: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during n8n interaction: {e}")
    
   # First create the Assignment
    assignment = Assignment(student_id=current_user.student_id, filename=file.filename)
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    # Then create the AnalysisResult linked to the Assignment
    analysis_result = AnalysisResult(assignment_id=assignment.id)
    db.add(analysis_result)
    await db.commit()
    await db.refresh(analysis_result)

    return {"analysis_id": analysis_result.id, "msg": "Analysis triggered. Results will be available shortly."}


@app.get("/analysis/{assignment_id}")
async def get_analysis(assignment_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    assignment_query = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id, Assignment.student_id == current_user.student_id)
    )
    assignment = assignment_query.scalar_one_or_none()

    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found or does not belong to user")

    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.assignment_id == assignment_id)
    )
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis results not yet available for this assignment.")
    
    return {
        "id": analysis.id,
        "assignment_id": analysis.assignment_id,
        "suggested_sources": analysis.suggested_sources,
        "plagiarism_score": analysis.plagiarism_score,
        "flagged_sections": analysis.flagged_sections,
        "research_suggestions": analysis.research_suggestions,
        "citation_recommendations": analysis.citation_recommendations,
        "confidence_score": analysis.confidence_score,
        "analyzed_at": analysis.analyzed_at.isoformat()
    }


@app.get("/sources")
async def get_sources(query: str, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    sources_raw = await search_sources(db, query)
    
    sources = []
    for row in sources_raw:
        sources.append({
            "id": row[0],
            "title": row[1],
            "authors": row[2],
            "publication_year": row[3],
            "abstract": row[4],
            "source_type": row[5]
        })
    return sources 