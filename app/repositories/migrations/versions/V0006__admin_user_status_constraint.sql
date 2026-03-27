UPDATE admin_users
SET status = CASE
    WHEN lower(trim(status)) IN ('enabled', 'active') THEN 'enabled'
    WHEN lower(trim(status)) = 'disabled' THEN 'disabled'
    ELSE 'disabled'
END;

DROP TRIGGER IF EXISTS tr_admin_users_status_insert;
CREATE TRIGGER tr_admin_users_status_insert
BEFORE INSERT ON admin_users
FOR EACH ROW
WHEN NEW.status NOT IN ('enabled', 'disabled')
BEGIN
    SELECT RAISE(ABORT, 'admin_users.status must be enabled or disabled');
END;

DROP TRIGGER IF EXISTS tr_admin_users_status_update;
CREATE TRIGGER tr_admin_users_status_update
BEFORE UPDATE OF status ON admin_users
FOR EACH ROW
WHEN NEW.status NOT IN ('enabled', 'disabled')
BEGIN
    SELECT RAISE(ABORT, 'admin_users.status must be enabled or disabled');
END;
