from fastapi import Depends

def get_current_user():
    return {"id": 1, "role": "admin"}

@router.get("/me")
async def me(user=Depends(get_current_user)):
    return user
