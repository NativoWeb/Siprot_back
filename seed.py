from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, User
from auth import get_password_hash
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def seed_superuser():
  db: Session = SessionLocal()
  
  try:
      Base.metadata.create_all(bind=engine)
    
      email="superadmin@gmail.com"
      hashed_password = get_password_hash("12345")
      first_name="super"
      last_name="admin"
      phone_number="123456789"
      
      role="superadmin"
      
      superuser = db.query(User).filter(
        (User.email == email)
      ).first()
      
      if superuser:
        superuser.password = hashed_password
        superuser.email = email
        superuser.first_name = first_name
        superuser.last_name = last_name
        superuser.phone_number = phone_number
        superuser.role = role
        db.add(superuser)
        
      else:
        new_superuser = User(
          email=email,
          password=hashed_password,
          first_name=first_name,
          last_name=last_name,
          phone_number=phone_number,
          role=role 
        )
        db.add(new_superuser)
        logger.info(f"Usuario '{new_superuser.first_name}' (instructor) creado en la base de datos.")
        
      db.commit()
      db.refresh(superuser if superuser else new_superuser)
      logger.info(f"Operación completada para el usuario '{superuser.first_name}'.")
  
  except Exception as e:
    db.rollback()
    logger.error(f"Error al crear/actualizar el usuario instructor: {e}")
  finally:
    db.close()
    
if __name__ == "__main__":
  seed_superuser()