package domain

import "fmt"

// DomainError is the base for all domain-layer errors. Adapters wrap raw
// driver errors into specific subtypes; HTTP handlers translate them.
type DomainError struct {
	Msg string
}

func (e *DomainError) Error() string { return e.Msg }

// CampNotFound is returned when a camp lookup by id misses.
type CampNotFound struct {
	CampID string
}

func (e *CampNotFound) Error() string { return fmt.Sprintf("camp not found: %s", e.CampID) }

// EmbeddingDimMismatch — used by D-3 vector adapter.
type EmbeddingDimMismatch struct{ Msg string }

func (e *EmbeddingDimMismatch) Error() string { return e.Msg }

// GeocodeUnresolved — used by geocode adapter.
type GeocodeUnresolved struct{ Msg string }

func (e *GeocodeUnresolved) Error() string { return e.Msg }

// EtaUnavailable — used by D-5 eta adapter.
type EtaUnavailable struct{ Msg string }

func (e *EtaUnavailable) Error() string { return e.Msg }

// GraphUnavailable — used by falkor adapter when FalkorDB is down.
type GraphUnavailable struct{ Msg string }

func (e *GraphUnavailable) Error() string { return e.Msg }

// SourceUnavailable — used by jsonl source when files are missing.
type SourceUnavailable struct{ Msg string }

func (e *SourceUnavailable) Error() string { return e.Msg }
