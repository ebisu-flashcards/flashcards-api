from typing import Optional

from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta
from fastapi import Depends, APIRouter, HTTPException, Response

# from fastapi.security import OAuth2PasswordRequestForm

import base64

from fastapi.encoders import jsonable_encoder

# from fastapi.security import OAuth2PasswordRequestForm, OAuth2
# from fastapi.security.base import SecurityBase
# from fastapi.security.utils import get_authorization_scheme_param
# from fastapi.openapi.docs import get_swagger_ui_html
# from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
# from fastapi.openapi.utils import get_openapi

# from starlette.status import HTTP_403_FORBIDDEN
# from starlette.responses import RedirectResponse, Response, JSONResponse
# from starlette.requests import Request


from flashcards_server import get_session, pwd_context
from flashcards_server.auth.cookie import BasicAuth
from flashcards_server.auth.models import User as UserModel
from flashcards_server.auth.functions import (
    get_current_user,
    create_access_token,
    authenticate_user,
)
from flashcards_server.constants import ACCESS_TOKEN_EXPIRE_MINUTES, DOMAIN


class UserBase(BaseModel):
    username: str
    email: str
    disabled: bool


class UserPatch(BaseModel):
    username: Optional[str]
    email: Optional[str]
    disabled: Optional[bool]


class User(UserBase):
    id: UUID

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


basic_auth = BasicAuth(auto_error=False)


@router.post("/register", response_model=User)
async def create_new_user(
    username: str, email: str, password: str, session: Session = Depends(get_session)
):
    hashed_password = pwd_context.hash(password)
    return UserModel.create(
        session=session, username=username, email=email, hashed_password=hashed_password
    )


@router.post("/login", response_model=Token)
async def login_basic(auth: BasicAuth = Depends(basic_auth)):
    if not auth:
        response = Response(headers={"WWW-Authenticate": "Basic"}, status_code=401)
        return response

    try:
        decoded = base64.b64decode(auth).decode("ascii")
        username, _, password = decoded.partition(":")
        user = authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect credentials")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )

        token = jsonable_encoder(access_token)

        response = Response({"message": "Logged in"})
        response.set_cookie(
            "Authorization",
            value=f"Bearer {token}",
            domain="localtest.me",
            httponly=True,
            max_age=1800,
            expires=1800,
        )
        return response

    except Exception:
        response = Response(headers={"WWW-Authenticate": "Basic"}, status_code=401)
        return response


# @router.post("/login", response_model=Token)
# async def login_for_access_token_and_cookie(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     session: Session = Depends(get_session),
# ):
#     user = authenticate(
#         username=form_data.username, password=form_data.password, session=session
#     )
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(
#         data_to_encode={"sub": user.username}, expires_delta=access_token_expires
#     )
#     response = Response({"message": "Logged in"})
#     response.set_cookie(
#         "Authorization",
#         value=f"Bearer {access_token}",
#         domain=DOMAIN,
#         httponly=True,
#         max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
#         expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
#     )
#     return response


@router.get("/logout")
async def route_logout_and_remove_cookie():
    response = Response({"message": "Logged out"})
    response.delete_cookie("Authorization", domain=DOMAIN)
    return response


@router.get("/user", response_model=User)
async def get_my_details(current_user: UserModel = Depends(get_current_user)):
    return current_user


@router.patch("/user", response_model=User)
async def update_my_details(
    new_user_data: UserPatch,
    current_user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    update_data = new_user_data.dict(exclude_unset=True)
    new_user_model = User(**vars(current_user)).copy(update=update_data)
    return UserModel.update(
        session=session, object_id=current_user.id, **new_user_model.dict()
    )


@router.delete("/user")
async def delete_my_user(
    current_user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    UserModel.delete(session=session, object_id=current_user.id)