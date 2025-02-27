# Services Guide

This document describes the service system in Transcribo.

## Overview

The service system provides:

1. Service lifecycle management
2. Dependency tracking and validation
3. Circular dependency detection
4. Service initialization
5. Configuration management
6. FastAPI integration

## Service Structure

All services inherit from `BaseService`:

```python
class MyService(BaseService):
    # Declare dependencies
    __dependencies__ = [DatabaseService, StorageService]
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        super().__init__(config)
        
    async def _initialize(self):
        # Initialization code here
        pass
```

## Service Dependencies

Dependencies can be declared in two ways:

1. Class-level declaration:
```python
class MyService(BaseService):
    __dependencies__ = [DatabaseService, StorageService]
```

2. Instance-level addition:
```python
service = MyService()
service.add_dependency(DatabaseService)
```

## Service Provider

The service provider manages service instances:

```python
# Register service
provider.register(DatabaseService, database_service)

# Get service
service = provider.get(DatabaseService)
```

Features:
- Singleton pattern
- Dependency validation
- Circular dependency detection
- Error tracking

## FastAPI Integration

Services can be used as FastAPI dependencies:

```python
@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    db: DatabaseService = Depends(get_service(DatabaseService))
):
    return await db.get_item(item_id)
```

Common dependencies are pre-defined:
```python
from backend.src.utils.dependencies import DatabaseServiceDep

@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    db: DatabaseServiceDep
):
    return await db.get_item(item_id)
```

## Service Initialization

Services can have asynchronous initialization:

```python
class DatabaseService(BaseService):
    async def _initialize(self):
        self.pool = await create_pool()
        await self.pool.connect()
```

Initialization is:
- Automatic when needed
- Idempotent (safe to call multiple times)
- Error-tracked

## Error Handling

Service errors include context:

```python
try:
    await service.initialize()
except ServiceError as e:
    print(f"Error: {e.message}")
    print(f"Service: {e.details['details']['service']}")
    print(f"Error details: {e.details['details']['error']}")
```

## Dependency Validation

The provider validates dependencies:

1. Missing dependencies:
```python
# Will raise DependencyError - DatabaseService not registered
provider.get(MyService)
```

2. Circular dependencies:
```python
# Will log warning - ServiceA depends on ServiceB which depends on ServiceA
provider.register(ServiceA, service_a)
provider.register(ServiceB, service_b)
```

## Best Practices

1. Declare dependencies at class level when possible
2. Initialize services in `_initialize` method
3. Use pre-defined dependencies in routes
4. Handle service errors appropriately
5. Keep services focused and single-purpose
6. Avoid circular dependencies
7. Use configuration for service settings

## Example Usage

### Service Definition

```python
class UserService(BaseService):
    __dependencies__ = [DatabaseService, CacheService]
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        super().__init__(config)
        self.db = None
        self.cache = None
    
    async def _initialize(self):
        # Get dependencies from provider
        provider = ServiceProvider()
        self.db = provider.get(DatabaseService)
        self.cache = provider.get(CacheService)
        
        # Initialize connection
        await self.db.initialize()
        await self.cache.initialize()
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        # Ensure initialized
        await self.initialize()
        
        # Try cache first
        user = await self.cache.get(f"user:{user_id}")
        if user:
            return user
        
        # Get from database
        user = await self.db.get_user(user_id)
        if user:
            await self.cache.set(f"user:{user_id}", user)
        
        return user
```

### Route Usage

```python
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user_service: UserService = Depends(get_service(UserService))
):
    try:
        user = await user_service.get_user(user_id)
        if not user:
            raise ResourceNotFoundError(f"User {user_id} not found")
        return user
        
    except ServiceError as e:
        # Service errors are automatically handled
        raise
        
    except Exception as e:
        # Convert other errors to TranscriboError
        raise ServiceError(
            f"Failed to get user: {str(e)}",
            details={
                "user_id": user_id,
                "error": str(e)
            }
        )
```

## Testing

Services can be easily tested:

```python
@pytest.mark.asyncio
async def test_user_service():
    # Create mock dependencies
    db = MockDatabaseService()
    cache = MockCacheService()
    
    # Create service
    provider = ServiceProvider()
    provider.register(DatabaseService, db)
    provider.register(CacheService, cache)
    
    service = UserService()
    await service.initialize()
    
    # Test methods
    user = await service.get_user("123")
    assert user is not None
