# Raw Data Inventory

- SQLite database: `travel_new.sqlite`
- FAQ document: `order_faq.md`

## Tables

| Table | Rows | Columns |
| --- | ---: | --- |
| `aircrafts_data` | 9 | aircraft_code, model, range |
| `airports_data` | 115 | airport_code, airport_name, city, coordinates, timezone |
| `boarding_passes` | 579686 | ticket_no, flight_id, boarding_no, seat_no |
| `bookings` | 262788 | book_ref, book_date, total_amount |
| `car_rentals` | 10 | id, name, location, price_tier, start_date, end_date, booked |
| `flights` | 33121 | flight_id, flight_no, scheduled_departure, scheduled_arrival, departure_airport, arrival_airport, status, aircraft_code, actual_departure, actual_arrival |
| `hotels` | 10 | id, name, location, price_tier, checkin_date, checkout_date, booked |
| `seats` | 1339 | aircraft_code, seat_no, fare_conditions |
| `ticket_flights` | 1045726 | ticket_no, flight_id, fare_conditions, amount |
| `tickets` | 366733 | ticket_no, book_ref, passenger_id |
| `trip_recommendations` | 10 | id, name, location, keywords, details, booked |

## FAQ Sections

| Section | Start line | Chars | Numbered items |
| --- | ---: | ---: | ---: |
| 发票问题 | 1 | 415 | 6 |
| 预订和取消 | 25 | 1541 | 19 |
| 预订平台 | 79 | 803 | 10 |
| 订购发票 | 102 | 373 | 0 |
| 信用卡 | 117 | 301 | 0 |
| 卡片安全 | 140 | 441 | 0 |
| 按发票支付 | 158 | 1322 | 0 |
| 常见问题：支付 | 212 | 424 | 0 |
| 常见问题：欧洲票价概念 | 237 | 1302 | 0 |
| 如何取消瑞士航空航班：877-5O7-7341 分步指南 | 284 | 3492 | 0 |
