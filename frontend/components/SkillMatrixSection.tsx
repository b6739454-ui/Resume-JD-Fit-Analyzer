import React, { useState } from 'react';
import type { SkillMatch } from '../types';

interface SkillMatrixSectionProps {
  matches: SkillMatch[];
}

type FilterCategory = 'all' | 'must_have' | 'nice_to_have';
type FilterStatus = 'all' | 'met' | 'partial' | 'missing';

const SkillMatrixSection: React.FC<SkillMatrixSectionProps> = ({ matches }) => {
  const [categoryFilter, setCategoryFilter] = useState<FilterCategory>('all');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');

  const filteredMatches = matches.filter((m) => {
    if (categoryFilter !== 'all' && m.category !== categoryFilter) return false;
    if (statusFilter !== 'all' && m.status !== statusFilter) return false;
    return true;
  });

  const getStatusBadge = (status: SkillMatch['status']) => {
    switch (status) {
      case 'met':
        return <span className="badge badge-met">Met</span>;
      case 'partial':
        return <span className="badge badge-partial">Partial</span>;
      case 'missing':
        return <span className="badge badge-missing">Missing</span>;
    }
  };

  const getCategoryBadge = (category: SkillMatch['category']) => {
    return category === 'must_have' ? (
      <span className="badge badge-must">Must-Have</span>
    ) : (
      <span className="badge badge-nice">Nice-to-Have</span>
    );
  };

  return (
    <section className="skill-matrix-section">
      <div className="matrix-header">
        <h3 className="matrix-title">Requirement Verification Matrix ({matches.length})</h3>

        <div className="matrix-filters">
          <div className="filter-group">
            <span className="filter-label">Priority:</span>
            <button
              className={`filter-btn ${categoryFilter === 'all' ? 'active' : ''}`}
              onClick={() => setCategoryFilter('all')}
            >
              All
            </button>
            <button
              className={`filter-btn ${categoryFilter === 'must_have' ? 'active' : ''}`}
              onClick={() => setCategoryFilter('must_have')}
            >
              Must-Have
            </button>
            <button
              className={`filter-btn ${categoryFilter === 'nice_to_have' ? 'active' : ''}`}
              onClick={() => setCategoryFilter('nice_to_have')}
            >
              Nice-to-Have
            </button>
          </div>

          <div className="filter-group">
            <span className="filter-label">Status:</span>
            <button
              className={`filter-btn ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              All
            </button>
            <button
              className={`filter-btn ${statusFilter === 'met' ? 'active' : ''}`}
              onClick={() => setStatusFilter('met')}
            >
              Met
            </button>
            <button
              className={`filter-btn ${statusFilter === 'partial' ? 'active' : ''}`}
              onClick={() => setStatusFilter('partial')}
            >
              Partial
            </button>
            <button
              className={`filter-btn ${statusFilter === 'missing' ? 'active' : ''}`}
              onClick={() => setStatusFilter('missing')}
            >
              Missing
            </button>
          </div>
        </div>
      </div>

      <div className="matrix-table-container">
        <table className="matrix-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Requirement</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Years Found</th>
              <th>Evidence from Resume</th>
            </tr>
          </thead>
          <tbody>
            {filteredMatches.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-table-cell">
                  No requirements match the selected filters.
                </td>
              </tr>
            ) : (
              filteredMatches.map((item) => (
                <tr key={item.requirement_index} className={`row-status-${item.status}`}>
                  <td className="cell-index">{item.requirement_index + 1}</td>
                  <td className="cell-skill">{item.skill}</td>
                  <td>{getCategoryBadge(item.category)}</td>
                  <td>{getStatusBadge(item.status)}</td>
                  <td className="cell-years">
                    {item.years_found !== null ? `${item.years_found} yrs` : '-'}
                  </td>
                  <td className="cell-evidence">
                    {item.evidence ? (
                      <blockquote className="evidence-quote">{item.evidence}</blockquote>
                    ) : (
                      <span className="no-evidence">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default SkillMatrixSection;
