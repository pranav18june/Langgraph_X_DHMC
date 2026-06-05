import { useState, useMemo } from 'react'
import { Search, ChevronDown, BookOpen } from 'lucide-react'
import { glossaryTerms } from '../data/glossary'
import './Glossary.css'

export default function Glossary() {
  const [query, setQuery] = useState('')
  const [expandedTerms, setExpandedTerms] = useState(new Set())

  const filteredTerms = useMemo(() => {
    if (!query.trim()) return glossaryTerms
    const q = query.toLowerCase()
    return glossaryTerms.filter(
      (term) =>
        term.term.toLowerCase().includes(q) ||
        term.plainEnglish.toLowerCase().includes(q) ||
        (term.technical && term.technical.toLowerCase().includes(q))
    )
  }, [query])

  const toggleExpand = (index) => {
    setExpandedTerms((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  return (
    <div className="glossary page">
      <div className="container">
        <div className="glossary__header">
          <h1>DHMC Glossary</h1>
          <p>
            Plain-English definitions for every cryptographic and audit term
            used in the DHMC system.
          </p>
        </div>

        <div className="glossary__search">
          <Search size={18} className="glossary__search-icon" />
          <input
            type="text"
            className="glossary__search-input"
            placeholder="Search terms…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search glossary terms"
          />
          <span className="glossary__search-count">
            {filteredTerms.length} term{filteredTerms.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="glossary__grid">
          {filteredTerms.length === 0 ? (
            <div className="glossary__no-results">
              <div className="glossary__no-results-icon">
                <BookOpen size={24} />
              </div>
              <h3>No terms found</h3>
              <p>Try a different search query.</p>
            </div>
          ) : (
            filteredTerms.map((term, i) => {
              const isOpen = expandedTerms.has(i)
              return (
                <div
                  className="glossary__card"
                  key={term.term}
                  style={{ animationDelay: `${150 + i * 60}ms` }}
                >
                  <div className="glossary__card-header">
                    <div className="glossary__card-icon">{term.icon}</div>
                    <div>
                      <div className="glossary__card-title">{term.term}</div>
                    </div>
                  </div>

                  <p className="glossary__card-explanation">
                    {term.plainEnglish}
                  </p>

                  {term.technical && (
                    <>
                      <button
                        className={`glossary__card-toggle ${isOpen ? 'glossary__card-toggle--open' : ''}`}
                        onClick={() => toggleExpand(i)}
                        aria-expanded={isOpen}
                      >
                        <ChevronDown size={14} />
                        {isOpen ? 'Hide' : 'Show'} technical definition
                      </button>

                      <div
                        className={`glossary__card-technical ${isOpen ? 'glossary__card-technical--open' : ''}`}
                      >
                        <div className="glossary__card-technical-inner">
                          {term.technical}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
