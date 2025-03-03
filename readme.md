# 기본 구상
 
- JSON 형식으로 데이터 전달
- `/game/ws/pong/<UUID>/<NAME>` 형태로 접근
  - TODO: 사용자 이름 말고 토큰을 넣어 인쯩까지 하는 구조도 좋을 듯
- 정상 종료시, 소켓 종료는 서버 책임
- 실행흐름
  1. 게임 채널 발급
  2. 게임 채널 접속
  3. 5선승제 게임 진행

# 채널 발급: (HTTP) 채널 생성 엔드포인트

> `/game/pong/new`

## 요청

- POST 요청
- 인증 토큰 필수
  - 쿠키로 전달 (`ford-johnson-sort`)
- 파라미터
  - 없음

## 응답

### JSON response

- result (bool): 매칭 성공 여부
- 요청 성공시
  - username (str): 사용자 이름
  - room_uuid (UUID): 게임 채널
- 요청 실패시
  - error (str): 실패 이유

### 예시

```json
{
    "result": true,
    "username": "ggori",
    "room_uuid": "943216f1-b145-489a-8485-2f536d6487f7"
}
```

```json
{
    "result": false,
    "error": "authentication error"
}
```


# 게임 진행: (WS) 서버 -> 클라이언트 메시지

## 메시지 형식

```json
{
  "type": <TYPE>,
  "data": <DATA>
}
```

## type `WAIT`

상대가 게임에 들어 오기 전, 대기 화면을 표시하기 위해 전달. 소켓 연결 직후 이 메시지를 받게 됨

### 자료

없음

### 예시

```json
{
  "type": "WAIT",
  "data": null
}
```

## type `READY`

상대가 입장해 게임을 시작하기 위해 전달. delay만큼의 시간을 기다린 이후, 서버는 공 움직임 이벤트(`move_ball`)를 보내 본격적인 게임의 시작을 알림

### 자료

- opponent (str): 상대 닉네임
- username (str): 본인 닉네임
- delay (int): 시작 전 대기시간

### 예시

```json
{
  "type": "READY",
  "data": {
    "opponent": "ggori",
    "username": "kyungjle",
    "delay": 3
  }
}
```

## type `MOVE_PADDLE`

서버는 항상 키보드 이벤트(`move_paddle`)를 전달

### 자료

- movement (enum): 움직임 종류. 이 플래그를 적용하여 상대의 움직임을 표현
  - `LEFT_START`: 왼쪽으로 움직이기 시작
  - `LEFT_END`: 왼쪽으로 움직임을 멈춤
  - `RIGHT_START`: 오른쪽으로 움직이기 시작
  - `RIGHT_END`: 오른쪽으로 움직임을 멈춤
- position (float): 패들 좌표. 이 값을 이용해 좌표를 보정

### 예시

```json
{
  "type": "MOVE_PADDLE",
  "data": {
    "movement": "LEFT_START",
    "position": 0.21
  }
}
```

## type `MOVE_BALL`

공의 가속도가 변화하는 이벤트(벽이나 패들에 닿는 경우)가 발생하면 변화를 전달

### 자료

- velocity (array): 공 가속도
  - float: x축 가속도
  - float: z축 가속도
- position (array): 보정을 위한 좌표
  - float: x 좌표
  - float: z 좌표

### 예시

```json
{
  "type": "MOVE_BALL",
  "data": {
    "velocity": [1.0, 0.0],
    "position": [5.0, 2.1]
  }
}
```

## type `END_ROUND`

라운드 종료를 알리는 메시지

### 자료

- win (bool): 플레이어가 이겼는지 여부
- score (array): 현재 점수
  - int: 플레이어 점수
  - int: 상대 점수

### 예시

```json
{
  "type": "END_ROUND",
  "data": {
    "win": true,
    "score": [4, 2]
  }
}
```

## type `END_GAME`

게임 종료를 알리는 메시지

### 자료

- win (bool): 플레이어가 이겼는지 여부
- score (array): 현재 점수
  - int: 플레이어 점수
  - int: 상대 점수
- reason (enum): 승리 이유
  - `SCORE`: 점수 승리
  - `ABANDON`: 상대가 접속 종료

### 예시

```json
{
  "type": "END_GAME",
  "data": {
    "win": true,
    "score": [1, 4],
    "reason": "ABANDON"
  }
}
```


# 게임 진행: (WS) 서버 -> 클라이언트 메시지

## 메시지 형식

```json
{
  "type": <TYPE>,
  "data": <DATA>
}
```

## type `MOVE_PADDLE`

키보드 이벤트(`move_paddle`)를 서버에

### 자료

- movement (enum): 움직임 종류. 이 플래그를 적용하여 움직임을 표현
  - `LEFT_START`: 왼쪽으로 움직이기 시작
  - `LEFT_END`: 왼쪽으로 움직임을 멈춤
  - `RIGHT_START`: 오른쪽으로 움직이기 시작
  - `RIGHT_END`: 오른쪽으로 움직임을 멈춤
- position (float): 패들 좌표. 이 값을 이용해 좌표를 보정

### 예시

```json
{
  "type": "MOVE_PADDLE",
  "data": {
    "movement": "LEFT_START",
  }
}
```
