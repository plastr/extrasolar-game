# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

from front.lib import db

class acquire_db_lock(object):
    """
    Context manager which uses the database to acquire a lock for the code running inside of the context.
    The code being protected can be run in different processes spaces or on different machines and the lock
    will hold.
    :param ctx: The database context, should be wrapped by commit_or_rollback or similar.
    :param lock_name: And string that uniquely identifies this lock.
    :param timeout: The number of seconds to wait to acquire the lock. Raises LockTimeoutError if
        timeout expires.
    :param raise_if_locked: Raises a LockAlreadyLocked exception if the lock is already held.
        See the helper class acquire_db_lock_if_unlocked.

    Use as::
        with db.commit_or_rollback(ctx) as ctx:
            with acquire_db_lock(ctx, 'LOCK_NAME', 10):
                code_protected_by_lock()
    """
    def __init__(self, ctx, lock_name, timeout=None, raise_if_locked=False):
        self.ctx = ctx
        self.lock_name = lock_name
        self.timeout = timeout
        # Attempt to open the database connection with a timeout of the lock timeout + 2 seconds.
        # That way if the lock times-out, an exception specific to that will be raised rather than
        # a generic socket timeout from the database connection library..
        if self.timeout is not None: self.timeout = self.timeout + 2
        self.raise_if_locked = raise_if_locked

    def __enter__(self):
        # Acquire the lock or wait for release.
        with db.conn(self.ctx, timeout=self.timeout) as ctx:
            # If requested, check to see if the lock is already acquired. If it is, raise LockAlreadyLocked.
            if self.raise_if_locked:
                if not is_lock_free(ctx, self.lock_name):
                    raise LockAlreadyLocked()

            res = db.row(ctx, 'locking/lock_acquire', lock_name=self.lock_name, timeout=self.timeout)['result']
            if res == 0:
                raise LockTimeoutError("Failed to acquire lock: %s timeout: %s" % (self.lock_name, self.timeout))
        return self

    def __exit__(self, exception_type, value, tb):
        with db.conn(self.ctx) as ctx:
            res = db.row(ctx, 'locking/lock_release', lock_name=self.lock_name)['result']
            if res == 0:
                raise LockUnlockError("Lock failed to unlock: %s timeout: %s" % (self.lock_name, self.timeout))

class acquire_db_lock_if_unlocked(acquire_db_lock):
    """
    Context manager which uses the database to acquire a lock for the code running inside of the context.
    This subclass of acquire_db_lock always raises a LockAlreadyLocked if the lock is currently held.
    See acquire_db_lock for full documentation.

    Use as::
        with db.commit_or_rollback(ctx) as ctx:
            try:
                with acquire_db_lock_if_unlocked(ctx, 'LOCK_NAME', 10):
                    code_protected_by_lock()
            except LockAlreadyLocked:
                code_to_run_if_lock_already_held()
    """
    def __init__(self, ctx, lock_name, timeout=None):
        super(acquire_db_lock_if_unlocked, self).__init__(ctx, lock_name, timeout=timeout, raise_if_locked=True)

def is_lock_free(ctx, lock_name):
    with db.conn(ctx) as ctx:
        is_free = db.row(ctx, 'locking/lock_is_free', lock_name=lock_name)['result']
        return bool(is_free)

class LockTimeoutError(Exception):
    pass

class LockUnlockError(Exception):
    pass

class LockAlreadyLocked(Exception):
    pass
