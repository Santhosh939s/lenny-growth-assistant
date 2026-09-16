import argparse
import sys
import logging
from app.db.session import SessionLocal
from app.services.ingestion_service import IngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def ingest():
    logger.info("Starting transcript ingestion...")
    db = SessionLocal()
    try:
        service = IngestionService(db)
        service.ingest_transcripts()
    finally:
        db.close()
    logger.info("Ingestion complete.")

def main():
    parser = argparse.ArgumentParser(description="Lenny Growth Assistant CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    ingest_parser = subparsers.add_parser("ingest", help="Ingest and embed transcripts into the knowledge base")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        ingest()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
