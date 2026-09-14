# EventCalendar Backend - API REST

Backend modular para **EventCalendar**, una API REST diseñada para gestionar eventos y sus planes de trabajo logísticos, desarrollada con **Django** y **Django REST Framework (DRF)**.

---

## 🚀 Stack Tecnológico

- **Framework**: Django 5.1+ & Django REST Framework
- **Base de Datos**: PostgreSQL alojado en Supabase (conexión directa mediante `DATABASE_URL` en `.env`; Supabase actúa únicamente como motor de base de datos)
- **Autenticación**: JSON Web Tokens vía `djangorestframework-simplejwt` (retorna `{ access, refresh }`)
- **Control de Acceso**: Permisos a nivel de objeto `IsOwner` (cada evento y tarea pertenece estrictamente a su creador)
- **CORS**: `django-cors-headers` configurado para interactuar con clientes frontend (Vite/React/Next.js)

---

## 📂 Estructura del Proyecto

```text
Backend/
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py         # Configuración general compartida
│   │   ├── dev.py          # Configuración de desarrollo (DEBUG=True)
│   │   └── prod.py         # Configuración de producción estricta
│   ├── __init__.py
│   ├── api_router.py       # Ensambla routers de cada app bajo /api/v1/
│   ├── urls.py             # Enrutamiento raíz
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/
│   │   ├── permissions.py  # IsOwner (valida que el recurso pertenezca a request.user)
│   │   └── exceptions.py   # Excepción personalizada HTTP 409 Conflict para sobrecarga diaria
│   ├── users/
│   │   ├── models.py       # User (extiende AbstractUser con daily_hour_limit)
│   │   ├── serializers.py
│   │   ├── views.py        # Registro, perfil y login JWT
│   │   └── urls.py
│   ├── events/
│   │   ├── models.py       # Event (user, title, description, event_date)
│   │   ├── serializers.py  # EventSerializer con progreso calculado
│   │   ├── views.py        # EventViewSet
│   │   ├── services.py     # Cálculo de progreso con prefetch_related("tasks")
│   │   └── tests.py
│   └── tasks/
│       ├── models.py       # TaskCategory, LogisticTask, RescheduleHistory
│       ├── serializers.py  # Serializers y validación de sobrecarga diaria
│       ├── views.py        # LogisticTaskViewSet, TaskCategoryViewSet, reprogramación e historial
│       ├── dashboard_views.py  # Vista "Hoy" y cálculo de carga
│       ├── services.py     # Tareas de hoy (select_related), carga diaria y regla de sobrecarga (> daily_hour_limit)
│       └── tests.py
├── requirements/
│   ├── base.txt            # Dependencias base
│   ├── dev.txt             # Dependencias de testing y linting
│   └── prod.txt            # Dependencias de producción (gunicorn)
├── manage.py
├── .env.example
└── README.md
```

---

## ⚙️ Configuración e Instalación

### 1. Requisitos previos
- Python 3.11+ (recomendado 3.12 o 3.14)
- Cuenta o proyecto en [Supabase](https://supabase.com) con PostgreSQL activo

### 2. Entorno virtual
```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
# En macOS / Linux:
source .venv/bin/activate
# En Windows:
# .venv\Scripts\activate

# Instalar dependencias de desarrollo
pip install -r requirements/dev.txt
```

### 3. Variables de Entorno
Copia el archivo de ejemplo y edita las credenciales:
```bash
cp .env.example .env
```
Edita `.env` con la cadena de conexión de tu base de datos Supabase:
```env
DATABASE_URL=postgresql://postgres:[TU_PASSWORD]@db.[TU_PROYECTO].supabase.co:5432/postgres
```

### 4. Migraciones
```bash
python manage.py makemigrations users events tasks
python manage.py migrate
```

### 5. Ejecutar Servidor Local
```bash
python manage.py runserver
```

---

## ⚡ Optimizaciones de Consulta (Prevención N+1)

1. **Vista "Hoy" / Carga Diaria**:
   - Implementada en `apps.tasks.services.TaskService.get_today_tasks`.
   - Utiliza `.select_related("event", "category")` para traer en una sola consulta SQL la tarea, su evento asociado y su categoría.

2. **Progreso de Eventos**:
   - Implementado en `apps.events.services.EventService.get_events_for_user`.
   - Utiliza `.prefetch_related("tasks")` para cargar todas las tareas asociadas en una sola consulta adicional, permitiendo que el cálculo de `progress_percentage`, `total_tasks` y `completed_tasks` se realice en memoria sin generar queries adicionales por cada evento (`O(1)` en lugar de `O(N)`).

---

## 🚦 Regla de Sobrecarga Diaria (HTTP 409 Conflict)

Cada usuario define su `daily_hour_limit` (por defecto `6.00` horas). 

Al intentar crear, editar o reprogramar una tarea:
- `TaskService.validate_daily_overload` calcula la suma de horas proyectadas para la fecha seleccionada.
- Si `horas_actuales + nuevas_horas > daily_hour_limit`, se interrumpe la operación y se responde con **HTTP 409 Conflict**:
```json
{
  "error": "DailyOverloadConflict",
  "detail": "La fecha 2026-09-20 excederá el límite diario de 6.00 horas. Horas actuales: 4.50, Horas a programar: 2.00.",
  "target_date": "2026-09-20",
  "current_hours": "4.50",
  "attempted_hours": "2.00",
  "daily_hour_limit": "6.00"
}
```

---

## 📡 Endpoints de la API (`/api/v1/`)

### Autenticación (`/api/v1/auth/`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register/` | Registro de usuario (retorna user + tokens `{ access, refresh }`) |
| `POST` | `/api/v1/auth/login/` | Login JWT (retorna `{ access, refresh, user }`) |
| `POST` | `/api/v1/auth/token/refresh/` | Refrescar token JWT |
| `GET` / `PUT` | `/api/v1/auth/profile/` | Ver y actualizar perfil (`daily_hour_limit`) |

### Eventos (`/api/v1/events/`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/events/` | Listar eventos con métricas de progreso prefetched |
| `POST` | `/api/v1/events/` | Crear nuevo evento |
| `GET` | `/api/v1/events/{id}/` | Detalle del evento |
| `PUT` / `PATCH` | `/api/v1/events/{id}/` | Modificar evento |
| `DELETE` | `/api/v1/events/{id}/` | Eliminar evento |

### Categorías de Tareas (`/api/v1/categories/`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/v1/categories/` | Listar y crear categorías únicas por usuario |
| `GET` / `PUT` / `DELETE` | `/api/v1/categories/{id}/` | Detalle, edición y borrado |

### Tareas Logísticas (`/api/v1/tasks/`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/v1/tasks/` | Listar y crear tareas logísticas (con validación 409) |
| `GET` / `PUT` / `DELETE` | `/api/v1/tasks/{id}/` | Detalle, edición y borrado |
| `POST` | `/api/v1/tasks/{id}/reschedule/` | Reprogramar fecha/horas con auditoría en `RescheduleHistory` |
| `GET` | `/api/v1/tasks/{id}/history/` | Consultar historial de reprogramaciones |

### Dashboard ("Hoy" y Carga Diaria) (`/api/v1/dashboard/`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/dashboard/today/` | Tareas de hoy con carga y estado de capacidad restante |
| `GET` | `/api/v1/dashboard/load/?date=YYYY-MM-DD` | Carga de trabajo para cualquier fecha específica |

---

## 🧪 Pruebas Unitarias

Ejecuta la suite de pruebas con:
```bash
python manage.py test
# o con pytest:
pytest
```
