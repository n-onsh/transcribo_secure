import os
import logging
from typing import List, Optional, Dict, Set
import json
from pathlib import Path
from datetime import datetime
from ..models.vocabulary import VocabularyList, VocabularyEntry, VocabularyUpdate

logger = logging.getLogger(__name__)

class VocabularyService:
    def __init__(self):
        """Initialize vocabulary service"""
        # Get configuration
        self.vocab_dir = Path(os.getenv("VOCAB_DIR", "data/vocabulary"))
        self.max_words = int(os.getenv("MAX_VOCAB_WORDS", "1000"))
        self.min_word_length = int(os.getenv("MIN_VOCAB_WORD_LENGTH", "2"))
        
        # Create directory if needed
        self.vocab_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for vocabulary lists
        self._cache: Dict[str, VocabularyList] = {}
        
        logger.info("Vocabulary service initialized")

    async def get_vocabulary(self, user_id: str) -> VocabularyList:
        """Get user's vocabulary list"""
        try:
            # Check cache first
            if user_id in self._cache:
                return self._cache[user_id]
            
            # Load from file
            vocab_file = self.vocab_dir / f"{user_id}.json"
            if vocab_file.exists():
                with open(vocab_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    vocab = VocabularyList.parse_obj(data)
            else:
                # Create new list
                vocab = VocabularyList(
                    user_id=user_id,
                    words=[],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            
            # Cache and return
            self._cache[user_id] = vocab
            return vocab
            
        except Exception as e:
            logger.error(f"Failed to get vocabulary: {str(e)}")
            raise

    async def update_vocabulary(
        self,
        user_id: str,
        update: VocabularyUpdate
    ) -> VocabularyList:
        """Update user's vocabulary list"""
        try:
            # Get current list
            vocab = await self.get_vocabulary(user_id)
            
            # Process words to add
            if update.add:
                new_words = set()
                for word in update.add:
                    # Clean and validate word
                    word = word.strip()
                    if len(word) >= self.min_word_length:
                        new_words.add(word)
                
                # Add new words
                existing_words = {e.word for e in vocab.words}
                for word in new_words:
                    if word not in existing_words:
                        vocab.words.append(VocabularyEntry(
                            word=word,
                            added_at=datetime.utcnow()
                        ))
                
                # Enforce max words limit
                if len(vocab.words) > self.max_words:
                    vocab.words = sorted(
                        vocab.words,
                        key=lambda e: e.added_at,
                        reverse=True
                    )[:self.max_words]
            
            # Process words to remove
            if update.remove:
                remove_set = {w.lower() for w in update.remove}
                vocab.words = [
                    e for e in vocab.words
                    if e.word.lower() not in remove_set
                ]
            
            # Update timestamp
            vocab.updated_at = datetime.utcnow()
            
            # Save changes
            await self._save_vocabulary(vocab)
            
            return vocab
            
        except Exception as e:
            logger.error(f"Failed to update vocabulary: {str(e)}")
            raise

    async def clear_vocabulary(self, user_id: str):
        """Clear user's vocabulary list"""
        try:
            # Create empty list
            vocab = VocabularyList(
                user_id=user_id,
                words=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Save changes
            await self._save_vocabulary(vocab)
            
        except Exception as e:
            logger.error(f"Failed to clear vocabulary: {str(e)}")
            raise

    async def delete_vocabulary(self, user_id: str):
        """Delete user's vocabulary list"""
        try:
            # Remove from cache
            self._cache.pop(user_id, None)
            
            # Delete file
            vocab_file = self.vocab_dir / f"{user_id}.json"
            if vocab_file.exists():
                vocab_file.unlink()
                
        except Exception as e:
            logger.error(f"Failed to delete vocabulary: {str(e)}")
            raise

    async def get_words(self, user_id: str) -> List[str]:
        """Get user's vocabulary words"""
        try:
            vocab = await self.get_vocabulary(user_id)
            return [e.word for e in vocab.words]
            
        except Exception as e:
            logger.error(f"Failed to get vocabulary words: {str(e)}")
            raise

    async def add_words(self, user_id: str, words: List[str]) -> VocabularyList:
        """Add words to vocabulary"""
        try:
            update = VocabularyUpdate(add=words)
            return await self.update_vocabulary(user_id, update)
            
        except Exception as e:
            logger.error(f"Failed to add vocabulary words: {str(e)}")
            raise

    async def remove_words(self, user_id: str, words: List[str]) -> VocabularyList:
        """Remove words from vocabulary"""
        try:
            update = VocabularyUpdate(remove=words)
            return await self.update_vocabulary(user_id, update)
            
        except Exception as e:
            logger.error(f"Failed to remove vocabulary words: {str(e)}")
            raise

    async def _save_vocabulary(self, vocab: VocabularyList):
        """Save vocabulary list to file"""
        try:
            # Update cache
            self._cache[vocab.user_id] = vocab
            
            # Save to file
            vocab_file = self.vocab_dir / f"{vocab.user_id}.json"
            with open(vocab_file, "w", encoding="utf-8") as f:
                json.dump(vocab.dict(), f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save vocabulary: {str(e)}")
            raise

    def _clean_word(self, word: str) -> str:
        """Clean and normalize word"""
        return word.strip().lower()

    def _validate_word(self, word: str) -> bool:
        """Validate word"""
        return len(word) >= self.min_word_length

    async def cleanup_old_vocabularies(self, days: int):
        """Delete vocabularies older than specified days"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            for vocab_file in self.vocab_dir.glob("*.json"):
                try:
                    with open(vocab_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        updated_at = datetime.fromisoformat(data["updated_at"])
                        
                    if updated_at < cutoff:
                        vocab_file.unlink()
                        user_id = vocab_file.stem
                        self._cache.pop(user_id, None)
                        
                except Exception as e:
                    logger.warning(f"Failed to process vocabulary file {vocab_file}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old vocabularies: {str(e)}")
            raise
