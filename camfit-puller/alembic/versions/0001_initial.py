"""initial schema

Revision ID: 0001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table("camps",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sido", sa.Text),
        sa.Column("sigungu", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("brief", sa.Text),
        sa.Column("location_brief", sa.Text),
        sa.Column("contact", sa.Text),
        sa.Column("price_start_from", sa.Integer),
        sa.Column("price_end_to", sa.Integer),
        sa.Column("num_of_reviews", sa.Integer, server_default="0"),
        sa.Column("num_of_viewed", sa.Integer, server_default="0"),
        sa.Column("bookmark_count", sa.Integer, server_default="0"),
        sa.Column("url", sa.Text),
        sa.Column("source", sa.Text, nullable=False, server_default="camfit"),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("geocoded_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("idx_camps_sido", "camps", ["sido"])
    op.create_index("idx_camps_sigungu", "camps", ["sigungu"])
    op.create_index("idx_camps_lat", "camps", ["lat"])
    op.create_index("idx_camps_lon", "camps", ["lon"])

    op.create_table("camp_descriptions",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("description", sa.Text),
    )

    # M:N tables sharing same shape pattern
    op.create_table("camp_types",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("type", sa.Text, primary_key=True),
    )
    op.create_table("camp_facilities",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("facility", sa.Text, primary_key=True),
        sa.Column("is_additional", sa.Boolean, server_default="false"),
    )
    op.create_table("camp_hashtags",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hashtag", sa.Text, primary_key=True),
    )
    op.create_table("camp_location_types",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("location_type", sa.Text, primary_key=True),
    )
    op.create_table("camp_collections",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_name", sa.Text, primary_key=True),
    )

    op.create_table("camp_medias",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idx", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text), sa.Column("thumb_url", sa.Text),
        sa.Column("w", sa.Integer), sa.Column("h", sa.Integer),
    )

    op.create_table("reviews",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_nick", sa.Text), sa.Column("season", sa.Text),
        sa.Column("user_type", sa.Text), sa.Column("num_of_days", sa.Integer),
        sa.Column("score", sa.Numeric(5,2)), sa.Column("text", sa.Text, nullable=False),
        sa.Column("is_clean", sa.Boolean), sa.Column("is_kind", sa.Boolean),
        sa.Column("is_manner", sa.Boolean), sa.Column("is_convenient", sa.Boolean),
        sa.Column("review_timestamp", sa.BigInteger),
    )
    op.create_index("idx_reviews_camp", "reviews", ["camp_id"])
    op.execute("CREATE INDEX idx_reviews_camp_score ON reviews (camp_id, score DESC)")
    op.create_table("review_medias",
        sa.Column("review_id", sa.Text, sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idx", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text),
    )

    op.create_table("camfit_filters",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("raw", postgresql.JSONB),
    )
    op.create_table("concepts",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("source", sa.Text, nullable=False, server_default="manual"),
        sa.Column("category", sa.Text), sa.Column("description", sa.Text),
        sa.Column("is_axis", sa.Boolean, server_default="false"),
    )
    op.create_table("filter_concept_mapping",
        sa.Column("filter_id", sa.Text, sa.ForeignKey("camfit_filters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("polarity", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("polarity IN (-1, 1)", name="polarity_check"),
    )
    for tbl in ("camp_filter_signals", "camp_desc_signals"):
        op.create_table(tbl,
            sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("score", sa.Numeric(5,4), nullable=False),
            sa.Column("evidence", sa.Text),
        )
    op.create_table("camp_review_signals",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Numeric(5,4), nullable=False),
        sa.Column("pos_count", sa.Integer, server_default="0"),
        sa.Column("neg_count", sa.Integer, server_default="0"),
        sa.Column("evidence", sa.Text),
    )
    op.execute("""
        CREATE MATERIALIZED VIEW camp_concept_aggregated AS
        SELECT camp_id, concept_id,
               COALESCE(SUM(f.score),0) * 1.0
             + COALESCE(SUM(r.score),0) * 0.7
             + COALESCE(SUM(d.score),0) * 0.5  AS final_score,
               array_remove(ARRAY[
                 CASE WHEN bool_or(f.score IS NOT NULL) THEN 'filter' END,
                 CASE WHEN bool_or(r.score IS NOT NULL) THEN 'review' END,
                 CASE WHEN bool_or(d.score IS NOT NULL) THEN 'description' END
               ], NULL) AS sources
        FROM (
          SELECT camp_id, concept_id FROM camp_filter_signals UNION
          SELECT camp_id, concept_id FROM camp_desc_signals UNION
          SELECT camp_id, concept_id FROM camp_review_signals
        ) all_sigs
        LEFT JOIN camp_filter_signals f USING (camp_id, concept_id)
        LEFT JOIN camp_review_signals r USING (camp_id, concept_id)
        LEFT JOIN camp_desc_signals   d USING (camp_id, concept_id)
        GROUP BY camp_id, concept_id;
    """)
    op.execute("CREATE INDEX idx_cca_concept_score ON camp_concept_aggregated (concept_id, final_score DESC)")

    op.execute("""
        CREATE TABLE camp_embeddings (
          camp_id text PRIMARY KEY REFERENCES camps(id) ON DELETE CASCADE,
          vec vector(768) NOT NULL,
          text_hash text NOT NULL,
          model_name text NOT NULL,
          created_at timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_camp_embeddings_hnsw ON camp_embeddings USING hnsw (vec vector_cosine_ops) WITH (m=16, ef_construction=64)")

    op.execute("""
        CREATE TABLE themes (
          id text PRIMARY KEY,
          label text NOT NULL,
          centroid vector(768),
          member_count integer DEFAULT 0,
          manual_label text,
          created_at timestamptz DEFAULT now()
        )
    """)
    op.create_table("camp_themes",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("theme_id", sa.Text, sa.ForeignKey("themes.id", ondelete="CASCADE")),
    )

    op.create_table("geocodes",
        sa.Column("query", sa.Text, primary_key=True),
        sa.Column("lat", sa.Float), sa.Column("lon", sa.Float),
        sa.Column("source", sa.Text), sa.Column("raw", postgresql.JSONB),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("eta_cache",
        sa.Column("origin", sa.Text, primary_key=True),
        sa.Column("dest", sa.Text, primary_key=True),
        sa.Column("minutes", sa.Integer), sa.Column("source", sa.Text),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS camp_concept_aggregated")
    for t in ("eta_cache","geocodes","camp_themes","themes","camp_embeddings",
              "camp_review_signals","camp_desc_signals","camp_filter_signals",
              "filter_concept_mapping","concepts","camfit_filters",
              "review_medias","reviews","camp_medias","camp_collections",
              "camp_location_types","camp_hashtags","camp_facilities","camp_types",
              "camp_descriptions","camps"):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
