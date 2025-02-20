from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Set
from datetime import datetime

class VocabularyEntry(BaseModel):
    """Vocabulary entry model"""
    word: str
    added_at: datetime = Field(default_factory=datetime.utcnow)

class VocabularyList(BaseModel):
    """Vocabulary list model"""
    user_id: str
    words: List[VocabularyEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_words(self) -> List[str]:
        """Get list of words"""
        return [entry.word for entry in self.words]

    def add_word(self, word: str):
        """Add word to list"""
        if word not in self.get_words():
            self.words.append(VocabularyEntry(word=word))
            self.updated_at = datetime.utcnow()

    def remove_word(self, word: str):
        """Remove word from list"""
        self.words = [e for e in self.words if e.word != word]
        self.updated_at = datetime.utcnow()

    def clear(self):
        """Clear all words"""
        self.words = []
        self.updated_at = datetime.utcnow()

    def contains(self, word: str) -> bool:
        """Check if word exists"""
        return word in self.get_words()

    def merge(self, other: "VocabularyList"):
        """Merge with another vocabulary list"""
        existing = set(self.get_words())
        for entry in other.words:
            if entry.word not in existing:
                self.words.append(entry)
        self.updated_at = datetime.utcnow()

class VocabularyUpdate(BaseModel):
    """Vocabulary update model"""
    add: Optional[List[str]] = None
    remove: Optional[List[str]] = None

    def apply_to(self, vocab: VocabularyList):
        """Apply update to vocabulary list"""
        if self.add:
            for word in self.add:
                vocab.add_word(word)
        if self.remove:
            for word in self.remove:
                vocab.remove_word(word)

class VocabularyFilter(BaseModel):
    """Vocabulary filter model"""
    prefix: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    added_after: Optional[datetime] = None
    added_before: Optional[datetime] = None

    def apply(self, vocab: VocabularyList) -> List[str]:
        """Apply filter to vocabulary list"""
        filtered = vocab.words
        
        if self.prefix:
            filtered = [e for e in filtered if e.word.startswith(self.prefix)]
            
        if self.min_length:
            filtered = [e for e in filtered if len(e.word) >= self.min_length]
            
        if self.max_length:
            filtered = [e for e in filtered if len(e.word) <= self.max_length]
            
        if self.added_after:
            filtered = [e for e in filtered if e.added_at >= self.added_after]
            
        if self.added_before:
            filtered = [e for e in filtered if e.added_at <= self.added_before]
            
        return [e.word for e in filtered]

class VocabularySort(BaseModel):
    """Vocabulary sort model"""
    field: str = Field(default="word")  # word, added_at
    ascending: bool = Field(default=True)

    def apply(self, vocab: VocabularyList) -> List[str]:
        """Apply sort to vocabulary list"""
        if self.field == "word":
            key = lambda e: e.word
        else:  # added_at
            key = lambda e: e.added_at
            
        sorted_entries = sorted(
            vocab.words,
            key=key,
            reverse=not self.ascending
        )
        
        return [e.word for e in sorted_entries]

class VocabularyStats(BaseModel):
    """Vocabulary statistics model"""
    total_words: int
    avg_word_length: float
    min_word_length: int
    max_word_length: int
    words_by_length: Dict[int, int]  # length -> count
    recently_added: List[str]  # last 10 words
    
    @classmethod
    def from_vocabulary(cls, vocab: VocabularyList) -> "VocabularyStats":
        """Generate statistics from vocabulary list"""
        words = vocab.get_words()
        lengths = [len(w) for w in words]
        
        by_length = {}
        for length in lengths:
            by_length[length] = by_length.get(length, 0) + 1
        
        return cls(
            total_words=len(words),
            avg_word_length=sum(lengths) / len(lengths) if lengths else 0,
            min_word_length=min(lengths) if lengths else 0,
            max_word_length=max(lengths) if lengths else 0,
            words_by_length=by_length,
            recently_added=[
                e.word for e in sorted(
                    vocab.words,
                    key=lambda e: e.added_at,
                    reverse=True
                )[:10]
            ]
        )
