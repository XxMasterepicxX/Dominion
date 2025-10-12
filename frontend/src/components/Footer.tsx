import './Footer.css';

export const Footer = () => {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div className="footer__identity">
          <span className="footer__title">Dominion</span>
          <p className="footer__tagline">Autonomous intelligence for real estate opportunity discovery.</p>
        </div>
        <div className="footer__meta">
          <span>(c) {new Date().getFullYear()} Dominion Labs</span>
          <span className="footer__sep">|</span>
          <a href="mailto:vasco.hinostroza@ieee.org">vasco.hinostroza@ieee.org</a>
        </div>
      </div>
    </footer>
  );
};
