from sqlalchemy import Column, Integer, String
from database import Base

class WordCard(Base):
    __tablename__ = "word_cards"

    id = Column(Integer, primary_key=True, index=True)
    english = Column(String, nullable=False)
    russian = Column(String, nullable=False)
    transcription = Column(String, nullable=True)
    example = Column(String, nullable=True)