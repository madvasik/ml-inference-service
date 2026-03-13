import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from backend.app.api.deps import get_current_user, get_current_admin
from backend.app.models.user import User, UserRole
from backend.app.auth.jwt import create_access_token, create_refresh_token


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    """Тест получения пользователя с невалидным токеном"""
    from backend.app.api.deps import security
    
    # Создаем мок credentials с невалидным токеном
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid_token"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_no_sub_in_token(db_session):
    """Тест получения пользователя с токеном без sub"""
    # Создаем токен без sub
    invalid_payload = {"type": "access"}
    token = create_access_token(invalid_payload)
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_refresh_token(db_session, test_user):
    """Тест получения пользователя с refresh токеном вместо access"""
    # Создаем refresh токен
    token = create_refresh_token({"sub": str(test_user.id)})
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_user_id(db_session):
    """Тест получения пользователя с невалидным user_id в токене"""
    # Создаем токен с невалидным user_id
    invalid_payload = {"sub": "not_a_number", "type": "access"}
    token = create_access_token(invalid_payload)
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid user ID" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_not_found(db_session):
    """Тест получения пользователя, которого нет в БД"""
    # Создаем токен для несуществующего пользователя
    token = create_access_token({"sub": "99999", "type": "access"})
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_admin_success(db_session, test_user):
    """Тест получения администратора"""
    from backend.app.auth.security import get_password_hash
    # Создаем администратора
    admin = User(
        email="admin_test@example.com",
        password_hash=get_password_hash("adminpassword"),
        role=UserRole.ADMIN
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    token = create_access_token({"sub": str(admin.id), "type": "access"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    # Сначала получаем пользователя
    current_user = await get_current_user(credentials, db_session)
    
    # Затем проверяем, что это администратор
    admin_user = await get_current_admin(current_user)
    
    assert admin_user.id == admin.id
    assert admin_user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_get_current_admin_forbidden(db_session, test_user):
    """Тест получения администратора для обычного пользователя"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    
    # Получаем пользователя
    current_user = await get_current_user(credentials, db_session)
    
    # Пытаемся получить администратора
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(current_user)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Admin access required" in exc_info.value.detail
