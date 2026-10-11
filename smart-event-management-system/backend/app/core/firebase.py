"""
Firebase Admin SDK initialization and Firestore client provider.

Supports:
1. Service Account JSON file path
2. Direct Firebase environment variables
3. Firestore Emulator
4. Application Default Credentials
"""

import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client, Transaction, transactional

from app.core.config import settings

logger = logging.getLogger("app.firebase")

_firestore_client: Optional[Client] = None


def init_firebase() -> Client:
    """Initialize Firebase Admin SDK and return Firestore client."""
    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    # ---------------------------------------------------------
    # 1. Firestore Emulator
    # ---------------------------------------------------------
    if settings.FIRESTORE_EMULATOR_HOST:
        os.environ["FIRESTORE_EMULATOR_HOST"] = (
            settings.FIRESTORE_EMULATOR_HOST
        )

        logger.info(
            "Using Firestore Emulator at %s",
            settings.FIRESTORE_EMULATOR_HOST,
        )

    # ---------------------------------------------------------
    # 2. Check whether Firebase is already initialized
    # ---------------------------------------------------------
    if not firebase_admin._apps:
        cred = None

        # -----------------------------------------------------
        # 3. Service-account JSON file
        # -----------------------------------------------------
        cred_path = (
            settings.FIREBASE_CREDENTIALS_PATH
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )

        if cred_path:
            if not os.path.isabs(cred_path):
                base_dir = os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.abspath(__file__)
                        )
                    )
                )

                cred_path = os.path.join(base_dir, cred_path)

            if os.path.exists(cred_path):
                logger.info(
                    "Initializing Firebase with credentials file: %s",
                    cred_path,
                )

                try:
                    cred = credentials.Certificate(cred_path)
                except Exception as e:
                    logger.error(
                        "Firebase credentials file could not be loaded: %s",
                        e,
                    )
                    cred = None
            else:
                logger.warning(
                    "Firebase credentials file not found at %s",
                    cred_path,
                )

        # -----------------------------------------------------
        # 4. Direct environment variables
        # -----------------------------------------------------
        if (
            not cred
            and settings.FIREBASE_PROJECT_ID
            and settings.FIREBASE_CLIENT_EMAIL
            and settings.FIREBASE_PRIVATE_KEY
        ):
            logger.info(
                "Initializing Firebase with environment variables"
            )

            # Convert literal \n characters from environment variables into
            # actual newline characters required by PEM format.
            private_key = settings.FIREBASE_PRIVATE_KEY.replace(
                "\\n",
                "\n",
            ).strip()

            # -------------------------------------------------
            # SAFE diagnostic - never prints the private key
            # -------------------------------------------------
            logger.info(
                "Firebase key diagnostic: starts=%s, ends=%s, length=%d",
                private_key.startswith(
                    "-----BEGIN PRIVATE KEY-----"
                ),
                private_key.endswith(
                    "-----END PRIVATE KEY-----"
                ),
                len(private_key),
            )

            cert_dict = {
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID.strip(),
                "private_key": private_key,
                "client_email": settings.FIREBASE_CLIENT_EMAIL.strip(),
                "token_uri": "https://oauth2.googleapis.com/token",
            }

            try:
                cred = credentials.Certificate(cert_dict)

                logger.info(
                    "Firebase certificate credentials created successfully."
                )

            except Exception as e:
                logger.error(
                    "Firebase environment credentials are invalid: %s",
                    e,
                )

                # Do not silently continue with invalid Firebase credentials.
                raise

        # -----------------------------------------------------
        # 5. Emulator / ADC fallback
        # -----------------------------------------------------
        if not cred:
            if settings.FIRESTORE_EMULATOR_HOST:
                logger.info(
                    "Initializing Firebase with default credentials "
                    "for Firestore Emulator"
                )

                project_id = (
                    settings.FIREBASE_PROJECT_ID
                    or "smart-event-management-demo"
                )

                firebase_admin.initialize_app(
                    options={
                        "projectId": project_id
                    }
                )

            else:
                try:
                    logger.info(
                        "Attempting Firebase initialization "
                        "with Application Default Credentials"
                    )

                    cred = credentials.ApplicationDefault()

                    project_id = (
                        settings.FIREBASE_PROJECT_ID or None
                    )

                    if project_id:
                        firebase_admin.initialize_app(
                            cred,
                            options={
                                "projectId": project_id
                            },
                        )
                    else:
                        firebase_admin.initialize_app(cred)

                except Exception as e:
                    logger.warning(
                        "Could not initialize Firebase with ADC: %s",
                        e,
                    )

                    project_id = (
                        settings.FIREBASE_PROJECT_ID
                        or "smart-event-management-demo"
                    )

                    firebase_admin.initialize_app(
                        options={
                            "projectId": project_id
                        }
                    )

        # -----------------------------------------------------
        # 6. Initialize Firebase with certificate credentials
        # -----------------------------------------------------
        else:
            options = {}
            project_id = settings.FIREBASE_PROJECT_ID or getattr(cred, "project_id", None)
            if project_id:
                options["projectId"] = project_id

            storage_bucket = (
                settings.FIREBASE_STORAGE_BUCKET
                or (f"{project_id}.firebasestorage.app" if project_id else None)
                or (f"{project_id}.appspot.com" if project_id else None)
            )
            if storage_bucket:
                options["storageBucket"] = storage_bucket

            if options:
                firebase_admin.initialize_app(cred, options=options)
            else:
                firebase_admin.initialize_app(cred)

            logger.info(
                "Firebase Admin SDK initialized successfully (Project: %s, Bucket: %s).",
                project_id,
                storage_bucket or "default",
            )

    # ---------------------------------------------------------
    # 7. Create Firestore client
    # ---------------------------------------------------------
    try:
        _firestore_client = firestore.client()

        logger.info(
            "Firestore client initialized successfully."
        )

        return _firestore_client

    except Exception as e:
        logger.error(
            "Failed to initialize Firestore client: %s",
            e,
        )
        raise


def get_firestore_db() -> Client:
    """Return Firestore client, initializing it if necessary."""
    global _firestore_client

    if _firestore_client is None:
        _firestore_client = init_firebase()

    return _firestore_client


def get_next_id(collection_name: str) -> int:
    """
    Generate a sequential integer ID for a Firestore collection.

    Uses a transaction first and falls back to a normal read/update
    if the transaction cannot be completed.
    """

    db = get_firestore_db()

    counter_ref = db.collection("_counters").document(
        collection_name
    )

    try:

        @transactional
        def _increment_counter_transaction(
            transaction: Transaction,
        ) -> int:

            snapshot = counter_ref.get(
                transaction=transaction
            )

            if snapshot.exists:
                current_id = int(
                    snapshot.get("current_id") or 0
                )

                new_id = current_id + 1

                transaction.update(
                    counter_ref,
                    {
                        "current_id": new_id
                    },
                )

            else:
                new_id = 1

                transaction.set(
                    counter_ref,
                    {
                        "current_id": 1
                    },
                )

            return new_id

        transaction = db.transaction()

        return _increment_counter_transaction(
            transaction
        )

    except Exception as e:

        logger.debug(
            "Transactional counter increment fallback: %s",
            e,
        )

        snapshot = counter_ref.get()

        if snapshot.exists:

            current_id = int(
                snapshot.get("current_id") or 0
            )

            new_id = current_id + 1

            counter_ref.update(
                {
                    "current_id": new_id
                }
            )

        else:

            new_id = 1

            counter_ref.set(
                {
                    "current_id": 1
                }
            )

        return new_id