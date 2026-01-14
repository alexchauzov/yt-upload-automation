# План рефакторинга архитектуры

## Проблема #1: Ошибка инициализации и нарушения архитектуры

### Договоренности

#### 1. Переименования

**Порты:**
- `ports/video_backend.py` → `ports/media_uploader.py`
- `ports/media_file_store.py` → `ports/media_store.py`

**Классы:**
- `VideoBackend` → `MediaUploader`
- `MediaFileStore` → `MediaStore`

**Адаптеры:**
- `adapters/youtube_backend.py` → `adapters/youtube_media_uploader.py`
- `adapters/local_media_file_store.py` → `adapters/local_media_store.py`

**Классы адаптеров (названия должны соответствовать портам):**
- `YouTubeApiBackend` → `YouTubeMediaUploader` (соответствует порту `MediaUploader`)
- `LocalMediaFileStore` → `LocalMediaStore` (соответствует порту `MediaStore`)

**Принцип именования:**
- Порт: `MediaUploader` → Адаптер: `{Platform}MediaUploader` (например, `YouTubeMediaUploader`, `InstagramMediaUploader`)
- Порт: `MediaStore` → Адаптер: `{Type}MediaStore` (например, `LocalMediaStore`, `S3MediaStore`)

**Исключения:**
- `VideoBackendError` → `MediaUploaderError`
- `RetryableError` → остается (может быть общим)
- `PermanentError` → остается (может быть общим)

#### 2. Архитектурные изменения

**Убираем:**
- ❌ Зависимость `MediaUploader` адаптера от другого адаптера
- ❌ Слой `MediaPreparer` (логика подготовки внутри адаптера)

**Добавляем:**
- ✅ `MediaUploader` (порт) принимает `VideoTask` + `media_ref: str`
- ✅ Адаптер сам решает, как обработать `media_ref`:
  - `YouTubeMediaUploader` использует `MediaStore` для получения локального `Path`
  - Будущий `InstagramMediaUploader` может работать с URL напрямую

#### 3. Сигнатуры интерфейсов

**`MediaUploader` (порт):**
```python
class MediaUploader(ABC):
    @abstractmethod
    def publish_media(self, task: VideoTask, media_ref: str) -> PublishResult:
        """
        Upload media to backend.
        
        Args:
            task: Media task with metadata (title, description, tags, etc.)
            media_ref: Media reference (path, URL, S3 key, blob ID, etc.)
                     Adapter decides how to handle it based on its needs.
        """
        pass
    
    @abstractmethod
    def upload_thumbnail(self, video_id: str, thumbnail_ref: str) -> bool:
        """
        Upload custom thumbnail for a media.
        
        Args:
            video_id: Backend media ID (e.g., YouTube video ID).
            thumbnail_ref: Thumbnail reference (path, URL, etc.)
                         Adapter decides how to handle it.
        """
        pass
```

**`MediaStore` (порт):**
```python
class MediaStore(ABC):
    @abstractmethod
    def exists(self, ref: str) -> bool:
        """Check if media reference exists."""
        pass
    
    @abstractmethod
    def get_path(self, ref: str) -> Path:
        """
        Resolve media reference to local Path (if needed by adapter).
        
        For local files: returns Path directly.
        For remote sources: may download and return local Path.
        """
        pass
    
    @abstractmethod
    def get_size(self, ref: str) -> int:
        """Get media size in bytes."""
        pass
    
    @abstractmethod
    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """Transition media to workflow stage."""
        pass
```

**`YouTubeMediaUploader` (адаптер):**
```python
class YouTubeMediaUploader(MediaUploader):
    def __init__(self, media_store: MediaStore):
        """
        YouTube adapter requires local file, so it uses MediaStore
        to resolve media_ref to local Path.
        """
        self.media_store = media_store
        # ... OAuth setup ...
    
    def publish_media(self, task: VideoTask, media_ref: str) -> PublishResult:
        # Adapter decides: YouTube needs local file
        video_path = self.media_store.get_path(media_ref)
        # Upload via YouTube API
        ...
```

#### 4. Domain-слой

**`PublishService`:**
- Использует `MediaStore` для валидации и transition файлов
- Использует `MediaUploader` (порт) для загрузки
- Передает `task` + `media_ref` в `MediaUploader`
- Не знает, как адаптер обработает `media_ref`

#### 5. Wiring в `app/main.py`

```python
# Создаем MediaStore
media_store = LocalMediaStore(base_path=storage_base_path)

# Создаем MediaUploader (адаптер сам решает как обработать media_ref)
media_uploader = YouTubeMediaUploader(media_store=media_store)

# Создаем PublishService
service = PublishService(
    metadata_repo=metadata_repo,
    media_store=media_store,
    media_uploader=media_uploader,
    ...
)
```

### Преимущества новой архитектуры

1. **Четкое разделение ответственности:**
   - Domain не знает о конкретных адаптерах
   - Адаптеры решают сами, как обрабатывать `media_ref`
   - Порты описывают контракты, не детали реализации

2. **Гибкость:**
   - Легко добавить новые источники медиа через `MediaStore` адаптеры
   - Легко добавить новые платформы через `MediaUploader` адаптеры
   - Адаптеры могут работать по-разному (локально, через URL, streaming)

3. **Изоляция:**
   - Domain зависит только от портов
   - Адаптеры могут зависеть от других адаптеров (это нормально)
   - Нет циклических зависимостей

### План реализации

1. Переименовать файлы и классы
2. Обновить сигнатуры интерфейсов
3. Обновить адаптеры
4. Обновить domain-слой
5. Обновить wiring в app/main.py
6. Обновить тесты
7. Обновить документацию
