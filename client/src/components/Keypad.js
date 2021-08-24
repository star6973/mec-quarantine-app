import "./Keypad.scss";
import React, { useState, useEffect, useRef } from "react";

const Keypad = () => {
    let [password, setPassWord] = useState("");

    const handleClickNumber = e => {
        e.preventDefault();
        password += e.currentTarget.innerText;
        console.log(e.currentTarget.innerText);
    }

    const handleClickClear = e => {
        e.preventDefault();
        console.log(e.currentTarget.innerText);
    }

    const handleClickEnter = e => {
        e.preventDefault();
        console.log(e.currentTarget.innerText);
    }

    useEffect(() => {
        let dots = document.getElementsByClassName("secure__dot");
        let keys = document.getElementsByClassName("secure__key");

        
    })

    return (
        <div className="password__ctrl">
            <div className="secure__top">
                <div className="robot__name">로봇</div>
                <div className="robot__tag">SeRo01</div>
                <div className="robot__service">방역안내</div>
            </div>
            <div className="secure__middle">
                <p>관리자 암호를 입력해주세요</p>
                <div className="secure__dots">
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                </div>
            </div>
            <div className="secure__bottom">
                <div className="secure__key__contianer">
                    <div className="secure__key" onClick={handleClickNumber}>1</div>
                    <div className="secure__key">2</div>
                    <div className="secure__key">3</div>
                    <div className="secure__key secure__key__clear" onClick={handleClickClear}>CLR</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">4</div>
                    <div className="secure__key">5</div>
                    <div className="secure__key">6</div>
                    <div className="secure__key">0</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">7</div>
                    <div className="secure__key">8</div>
                    <div className="secure__key">9</div>
                    <div className="secure__key secure__key__enter" onClick={handleClickEnter}>Enter</div>
                </div>
            </div>
        </div>
    )
}

export default Keypad;