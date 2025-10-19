import { Link, NavLink, useLocation } from 'react-router-dom';
import logo from '../assets/logo.png';
import './Navigation.css';

const NAV_ITEMS = [
  { label: 'Overview', to: '/' },
  { label: 'Capabilities', to: '/#capabilities' },
  { label: 'Signals', to: '/#signals' },
  { label: 'Projects', to: '/projects' },
];

export const Navigation = () => {
  const { pathname } = useLocation();

  return (
    <header className="nav">
      <div className="nav__inner">
        <Link to="/" className="nav__brand">
          <img src={logo} alt="Dominion logo mark" className="nav__logo" />
          <div className="nav__brand-text">
            <span className="nav__brand-name">Dominion</span>
            <span className="nav__brand-tag">Real Estate Intelligence</span>
          </div>
        </Link>
        <nav className="nav__links" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            if (item.to.includes('#')) {
              const [route, hash] = item.to.split('#');
              const isActive = route === pathname && hash.length > 0;
              return (
                <a key={item.label} className={`nav__link ${isActive ? 'nav__link--active' : ''}`} href={item.to}>
                  {item.label}
                </a>
              );
            }

            return (
              <NavLink
                key={item.label}
                to={item.to}
                className={({ isActive }) => `nav__link ${isActive ? 'nav__link--active' : ''}`}
              >
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        {/* CTA removed per request */}
      </div>
    </header>
  );
};
