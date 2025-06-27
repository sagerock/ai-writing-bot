import React from 'react';
import AccountPanel from './AccountPanel';
import { Link } from 'react-router-dom';

const AccountPage = ({ auth }) => {
    return (
        <div className="account-page">
            <nav className="account-nav">
                <Link to="/">&larr; Back to Chat</Link>
            </nav>
            <AccountPanel auth={auth} />
        </div>
    );
};

export default AccountPage; 