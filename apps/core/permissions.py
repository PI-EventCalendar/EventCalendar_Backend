from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Object-level permission that allows access only to the owner of the resource.
    Resolves `obj.user` if available, or tests direct ownership `obj == request.user`.
    For nested objects like LogisticTask whose direct parent is an event, resolves `obj.event.user`.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "event") and hasattr(obj.event, "user"):
            return obj.event.user == request.user
        if hasattr(obj, "task") and hasattr(obj.task, "user"):
            return obj.task.user == request.user
        return obj == request.user
