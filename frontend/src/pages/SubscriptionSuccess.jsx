import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const SubscriptionSuccess = () => {
    const [countdown, setCountdown] = useState(5);
    const navigate = useNavigate();

    useEffect(() => {
        const timer = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) {
                    clearInterval(timer);
                    navigate('/chat');
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [navigate]);

    return (
        <div className="subscription-success">
            <div className="success-container">
                <div className="success-icon">✓</div>
                <h1>Welcome to RomaLume!</h1>
                <p className="success-message">
                    Your subscription is now active. Thank you for supporting
                    <strong> Houseless Movement</strong>!
                </p>

                <div className="impact-message">
                    <p>
                        Every month, your subscription helps provide shelter and support
                        to homeless individuals in Akron, Ohio.
                    </p>
                </div>

                <div className="next-steps">
                    <h3>What's Next?</h3>
                    <ul>
                        <li>Start chatting with 12+ AI models</li>
                        <li>Upload documents for AI-powered search</li>
                        <li>Check your impact in Account settings</li>
                    </ul>
                </div>

                <p className="redirect-notice">
                    Redirecting to chat in {countdown} seconds...
                </p>

                <button onClick={() => navigate('/chat')} className="btn-primary">
                    Start Chatting Now
                </button>
            </div>
        </div>
    );
};

export default SubscriptionSuccess;
